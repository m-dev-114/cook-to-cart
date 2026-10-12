"""Real Swiggy Instamart MCP client: OAuth 2.1 + PKCE (dynamic client registration) and MCP streamable HTTP.
Built from Swiggy's published docs (auth flow, search_products / get_cart / update_cart schemas). Checkout and payment tools are NOT allowed."""
import asyncio, base64, hashlib, json, os, re, secrets, time
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

BASE = os.getenv("SWIGGY_BASE", "https://mcp.swiggy.com").rstrip("/")
MCP_URL = os.getenv("SWIGGY_MCP_URL", BASE + "/im")
REDIRECT = os.getenv("SWIGGY_REDIRECT_URI", "http://localhost:8000/api/swiggy/callback")
FRONTEND = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
PROTO = "2025-03-26"
READ = {"get_addresses", "search_products", "get_cart"}  # least privilege: only tools this app uses
CONFIRM = {"update_cart", "clear_cart", "create_address"}  # mutating: only with confirmed=True
TICKETS = {}  # one-time, 60-second sign-in tickets
TOKENS, PENDING, CLIENT = {}, {}, {"id": os.getenv("SWIGGY_CLIENT_ID")}  # tokens live in server memory only
SID = r"^[A-Za-z0-9-]{8,64}$"
BACKOFF = (0.5, 1.5)  # bounded waits between retries of READ calls only; mutations are never retried


class NeedLogin(Exception): pass
class SwiggyError(Exception):
    def __init__(self, msg, kind="MCP_UPSTREAM_ERROR"): super().__init__(msg); self.kind = kind


_PU = {"kg": ("g", 1000), "g": ("g", 1), "gm": ("g", 1), "gms": ("g", 1), "ml": ("ml", 1), "l": ("ml", 1000), "ltr": ("ml", 1000), "ltrs": ("ml", 1000),
       "litre": ("ml", 1000), "litres": ("ml", 1000), "liter": ("ml", 1000), "liters": ("ml", 1000), "pc": ("piece", 1), "pcs": ("piece", 1),
       "piece": ("piece", 1), "pieces": ("piece", 1), "unit": ("piece", 1), "units": ("piece", 1), "nos": ("piece", 1)}


def parse_pack(desc):
    """'500 g' / '1 L' / '2 x 100 g' / 'Pack of 6' -> (quantity in g|ml|piece, unit); None if it can't be read (product is then not offered)."""
    s = str(desc or "").lower().replace("×", "x")
    m = re.search(r"(?:(\d+)\s*x\s*)?(\d+(?:\.\d+)?)\s*(kgs?|gms?|g|ml|ltrs?|litres?|liters?|l|pcs?|pieces?|units?|nos)\b", s)
    if m:
        base, f = _PU["kg" if m.group(3) == "kgs" else m.group(3)]
        return round(int(m.group(1) or 1) * float(m.group(2)) * f, 2), base
    m = re.search(r"(\d+(?:\.\d+)?)\s*(bunch(?:es)?|combo)\b", s)  # fresh herbs/greens are sold by the bunch: dropping them made "mint leaves" look unavailable
    if m: return float(m.group(1)), ("combo" if m.group(2) == "combo" else "bunch")
    m = re.search(r"pack of (\d+)", s)
    return (float(m.group(1)), "piece") if m else None


def _money(v):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(v or "")); 
    try: return float(m.group(0).replace(",", "")) if m else None
    except ValueError: return None


def _cl(v, n): return re.sub(r"[<>]", "", str(v or "")).strip()[:n]


BUNDLE = re.compile(r"\bx\s*\d+\s*$", re.I)
_TAG = ("tag", "addressTag", "annotation", "label", "name", "type", "addressType", "nickname")
_LINE = ("flatNo", "houseNo", "flat", "building", "buildingName", "address", "addressLine", "addressLine1", "addressLine2", "formattedAddress", "fullAddress", "displayAddress", "street", "landmark", "area", "locality", "sublocality", "city", "pincode", "zipcode", "postalCode")
_IDLIKE = re.compile(r"^[A-Za-z0-9_\-]{16,}$")


def fmt_address(a, i=1):
    """Human-readable address from whatever fields Swiggy returns. The opaque id is NEVER shown; the id stays internal for MCP calls."""
    flat = {}
    def walk(o, d=0):
        for k, v in (o.items() if isinstance(o, dict) else []):
            if isinstance(v, dict) and d < 2: walk(v, d + 1)
            elif isinstance(v, (str, int)) and not isinstance(v, bool): flat.setdefault(k, str(v).strip())
    walk(a)
    ok = lambda v: v and not _IDLIKE.match(v) and v.lower() not in ("none", "null")
    tag = next((flat[k] for k in _TAG if ok(flat.get(k))), "")
    parts = [flat[k] for k in _LINE if ok(flat.get(k))]
    if not parts:  # unknown field names: any readable text value that is not an id
        parts = [v for k, v in flat.items() if k.lower() not in ("id", "addressid", "userid") and not k.lower().endswith("id") and ok(v) and not re.fullmatch(r"[\d.\-]+", v) and v != tag]
    seen, out = set(), []
    for p in parts:
        if p.lower() not in seen and not any(p.lower() in o.lower() for o in out): seen.add(p.lower()); out.append(p)
    out = [o for o in (re.sub(r"\S{16,}", lambda m: "" if _IDLIKE.match(m.group(0)) and re.search(r"\d", m.group(0)) else m.group(0), x).strip(" ,") for x in out) if o]  # an opaque id inside any text field is dropped
    body = ", ".join(out[:5])
    if tag and body.lower().startswith(tag.lower()): return _cl(body, 160)  # "Demo: Demo: ..." -> "Demo: ..."
    if tag and body: return _cl(f"{tag}: {body}", 160)
    return _cl(body or tag or f"Saved address {i} (Swiggy gave no readable details; check it in the Swiggy app)", 160)


class SwiggyInstamartMCPClient:
    label = "SWIGGY INSTAMART (connect your account)"  # the UI only says LIVE after a real MCP call has succeeded

    def __init__(self, transport=None):
        self.transport, self._http, self.mcp, self.seen, self.cart_addr, self.locks, self.sems = transport, None, {}, {}, {}, {}, {}
        self.totals, self.bills, self.adjust = {}, {}, {}

    def http(self):
        if self._http is None: self._http = httpx.AsyncClient(timeout=25, transport=self.transport)
        return self._http

    def _lock(self, sid): return self.locks.setdefault((id(asyncio.get_running_loop()), sid), asyncio.Lock())
    def _sem(self): return self.sems.setdefault(id(asyncio.get_running_loop()), asyncio.Semaphore(3))  # at most 3 MCP calls in flight

    async def _post(self, sid, body, retry=False):
        t = TOKENS.get(sid)
        if not t or t["exp"] < time.time(): raise NeedLogin()
        h = {"Authorization": "Bearer " + t["token"], "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTO}
        if self.mcp.get(sid): h["Mcp-Session-Id"] = self.mcp[sid]
        n = len(BACKOFF) + 1 if retry else 1
        for a in range(n):
            last = a == n - 1
            try: r = await self.http().post(MCP_URL, json=body, headers=h)
            except httpx.HTTPError as e:
                if not last: await asyncio.sleep(BACKOFF[a]); continue
                to = isinstance(e, httpx.TimeoutException)
                raise SwiggyError("Swiggy took too long to respond." if to else "Couldn't reach Swiggy right now.", "MCP_TIMEOUT" if to else "MCP_UPSTREAM_ERROR")
            if r.status_code in (401, 419): TOKENS.pop(sid, None); self.mcp.pop(sid, None); raise NeedLogin()
            if r.status_code in (429, 502, 503, 504) and not last:
                try: ra = float(r.headers.get("retry-after", 0))
                except ValueError: ra = 0
                await asyncio.sleep(min(ra or BACKOFF[a], 5)); continue
            if r.status_code == 429: raise SwiggyError("Swiggy is temporarily rate-limiting requests. Please wait a minute and try again.", "MCP_RATE_LIMITED")
            if r.status_code >= 400: raise SwiggyError(f"Swiggy returned an error ({r.status_code}).", "MCP_UPSTREAM_ERROR")
            return r

    @staticmethod
    def _parse(r):
        if "text/event-stream" in r.headers.get("content-type", ""):
            msgs = [json.loads(l[5:].strip()) for l in r.text.splitlines() if l.startswith("data:") and l[5:].strip()]
            return next((m for m in reversed(msgs) if "result" in m or "error" in m), {})
        return r.json() if r.content else {}

    async def _ensure(self, sid):
        async with self._lock(sid):  # parallel searches must not each open their own MCP session
            if sid in self.mcp: return
            r = await self._post(sid, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": PROTO, "capabilities": {},
                                                                                                  "clientInfo": {"name": "cook-to-cart", "version": "1"}}}, retry=True)
            self.mcp[sid] = r.headers.get("mcp-session-id", "")
            await self._post(sid, {"jsonrpc": "2.0", "method": "notifications/initialized"}, retry=True)

    async def call(self, sid, tool, args, confirmed=False):
        if tool not in READ | CONFIRM or (tool in CONFIRM and not confirmed): raise PermissionError(f"MCP tool '{tool}' is not permitted")
        await self._ensure(sid)
        async with self._sem():
            r = await self._post(sid, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool, "arguments": args}}, retry=tool in READ)
        try: msg = self._parse(r)
        except ValueError: raise SwiggyError("Unexpected response from Swiggy.", "MCP_BAD_RESPONSE")
        if "error" in msg: raise SwiggyError(_cl((msg["error"] or {}).get("message"), 160) or "Swiggy request failed.")
        res = msg.get("result") or {}; env = res.get("structuredContent")
        for part in ([] if isinstance(env, dict) else res.get("content", [])):
            if part.get("type") == "text":
                try: env = json.loads(part["text"]); break
                except ValueError: pass
        if not isinstance(env, dict): raise SwiggyError("Unexpected response from Swiggy.", "MCP_BAD_RESPONSE")
        if res.get("isError") or env.get("success") is False: raise SwiggyError(_cl((env.get("error") or {}).get("message"), 160) or "Swiggy request failed.")
        return env.get("data", env)

    async def create_address(self, sid, a):
        """Official create_address tool, only the documented parameters. Server geocodes when lat/long are omitted."""
        d = await self.call(sid, "create_address", {k: v for k, v in a.items() if v not in (None,)}, confirmed=True)
        aid = d.get("addressId") if isinstance(d, dict) else None
        if not aid: raise SwiggyError("Swiggy did not confirm the new address.")
        return str(aid)

    async def clear_cart(self, sid): await self.call(sid, "clear_cart", {}, confirmed=True)

    async def addresses(self, sid="demo"):
        d = await self.call(sid, "get_addresses", {})
        raw = [a for a in (d.get("addresses") or []) if isinstance(a, dict) and a.get("id")]
        if raw and not getattr(self, "_logged_addr_keys", False): self._logged_addr_keys = True; print("get_addresses fields:", sorted({k for a in raw for k in a}))  # field NAMES only, never values
        return [{"id": str(a["id"]), "label": fmt_address(a, i)} for i, a in enumerate(raw, 1)]

    async def search(self, q, address_id=None, sid="demo"):
        if not address_id: raise SwiggyError("Choose a delivery address first.")
        d = await self.call(sid, "search_products", {"addressId": address_id, "query": _cl(q, 100)})
        out, ids, sigs = [], set(), set()
        for pr in (d.get("products") or [])[:20]:
            vs = pr.get("variations") or []
            vs = [v for v in vs if not BUNDLE.search(str(v.get("quantityDescription") or ""))] or vs  # "20 g x 2" bundles are just 2 packs: the pack counter covers that
            for v in vs[:8]:
                if not (v.get("spinId") and v.get("skuId")): continue
                pk = parse_pack(v.get("quantityDescription")); price = (v.get("price") or {}).get("offerPrice")
                try: rating = float((v.get("rating") or {}).get("value")) or None
                except (TypeError, ValueError): rating = None
                try: price = float(price)
                except (TypeError, ValueError): price = None
                p = dict(product_id=str(v["spinId"]), name=_cl(v.get("displayName") or pr.get("displayName"), 200), brand=_cl(v.get("brandName") or pr.get("brand"), 80) or None,
                         category=None, variant=None, pack_quantity=pk[0] if pk else None, pack_unit=pk[1] if pk else None, pack_label=_cl(v.get("quantityDescription"), 40) or None,
                         price=price, availability=bool(v.get("isInStockAndAvailable")) and pr.get("inStock", True) is not False,
                         image_url=(u if isinstance(u := v.get("imageUrl"), str) and u.startswith("https://") and len(u) <= 500 else None), rating=rating)
                self.seen[(sid, p["product_id"])] = {**p, "sku_id": str(v["skuId"])}
                sig = (p["name"].lower(), (p["brand"] or "").lower(), p["pack_label"], p["price"])
                if p["product_id"] in ids or sig in sigs: continue  # the same listing returned twice: show it once
                ids.add(p["product_id"]); sigs.add(sig); out.append(p)
        return out

    async def known(self, pid, sid="demo"): return self.seen.get((sid, pid))  # only products Swiggy actually returned to this session

    async def revalidate(self, pid, sid="demo", address_id=None):
        """Fresh live check: search again and require the same variation (spinId) to still be listed. Returns the live product (live price/stock) or None."""
        k, addr = self.seen.get((sid, pid)), address_id or self.cart_addr.get(sid)
        if not k or not addr: return None
        return next((p for p in await self.search(k["name"], addr, sid) if p["product_id"] == pid), None)

    async def get_cart(self, sid):
        d = await self.call(sid, "get_cart", {})
        self.cart_addr[sid] = (d.get("selectedAddressDetails") or {}).get("id")
        bb = d.get("billBreakdown") if isinstance(d.get("billBreakdown"), dict) else {}  # real schema: lineItems[{label,value}] + toPay{label,value}; no fixed fee field names
        lines = [{"label": _cl(x.get("label"), 60), "value": _cl(x.get("value"), 30)} for x in (bb.get("lineItems") or []) if isinstance(x, dict) and x.get("label")][:15]
        tp = bb.get("toPay") if isinstance(bb.get("toPay"), dict) else {}
        self.bills[sid] = {"lines": lines, "to_pay": _cl(tp.get("value"), 30) or None, "to_pay_amount": _money(tp.get("value"))} if (lines or tp) else None
        try: self.totals[sid] = float(d.get("cartTotalAmount"))
        except (TypeError, ValueError): self.totals.pop(sid, None)
        if d.get("cartAbsent"): return []
        if any(not (isinstance(i, dict) and i.get("spinId") and i.get("skuId")) for i in (d.get("items") or [])):  # update_cart REPLACES the cart: never write one we couldn't fully read
            raise SwiggyError("Your Swiggy cart has items this app can't read safely, so it won't touch the cart. Edit the cart in the Swiggy app first.")
        return [{"product_id": str(i["spinId"]), "sku_id": str(i.get("skuId", "")), "packs": int(i.get("quantity") or 1), "price": i.get("discountedFinalPrice"),
                 "name": _cl(f'{i.get("itemName", "")} ({i["itemVariant"]})' if i.get("itemVariant") else i.get("itemName"), 200)}
                for i in (d.get("items") or []) if isinstance(i, dict) and i.get("spinId")]

    async def update_cart(self, sid, items, address_id=None):
        addr = address_id or self.cart_addr.get(sid)
        if not addr: raise SwiggyError("Choose a delivery address first.")
        payload = []
        for it in items:  # Swiggy REPLACES the whole cart: `items` must already be existing + new
            sku = it.get("sku_id") or (self.seen.get((sid, it["product_id"])) or {}).get("sku_id")
            if not sku: raise SwiggyError("A cart item has no SKU; search again.")
            payload.append({"spinId": it["product_id"], "skuId": sku, "quantity": int(it["packs"])})
        d = await self.call(sid, "update_cart", {"selectedAddressId": addr, "items": payload}, confirmed=True)
        d = d if isinstance(d, dict) else {}  # documented extras: removedOutOfStockItems[], reducedQuantityItems[{spinId,itemName,requestedQuantity,cappedQuantity,reason}]
        self.adjust[sid] = {"removed": [_cl(i.get("itemName"), 80) for i in (d.get("removedOutOfStockItems") or []) if isinstance(i, dict)][:20],
                            "reduced": [{"name": _cl(i.get("itemName"), 80), "requested": i.get("requestedQuantity"), "capped": i.get("cappedQuantity"), "reason": _cl(i.get("reason"), 120) or None} for i in (d.get("reducedQuantityItems") or []) if isinstance(i, dict)][:20]}


def make_router(client):
    r = APIRouter(prefix="/api/swiggy")
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    async def register():
        if CLIENT["id"]: return CLIENT["id"]
        try:
            x = await client.http().post(BASE + "/auth/register", json={"client_name": "Cook to Cart (local dev)", "redirect_uris": [REDIRECT],
                "grant_types": ["authorization_code"], "response_types": ["code"], "token_endpoint_auth_method": "none", "scope": "mcp:tools"})
            x.raise_for_status(); CLIENT["id"] = x.json()["client_id"]
        except Exception: raise HTTPException(502, "Couldn't start Swiggy sign-in right now.")
        return CLIENT["id"]

    @r.post("/login-start")
    async def login_start(request: Request):
        sid = request.headers.get("x-session", "")
        if not re.match(SID, sid): raise HTTPException(400, "Invalid session.")
        now = time.time()
        for k in [k for k, v in TICKETS.items() if v["exp"] < now]: TICKETS.pop(k)
        t = secrets.token_urlsafe(24); TICKETS[t] = {"sid": sid, "exp": now + 60}
        return {"ticket": t}

    @r.get("/login")
    async def login(ticket: str = Query(..., min_length=16, max_length=64)):
        tk = TICKETS.pop(ticket, None)  # single use: a URL in history or logs can't be replayed
        if not tk or tk["exp"] < time.time(): raise HTTPException(400, "The sign-in link expired. Please click Connect again.")
        sid = tk["sid"]
        cid = await register(); now = time.time()
        for k in [k for k, v in PENDING.items() if v["exp"] < now]: PENDING.pop(k)
        verifier = secrets.token_urlsafe(48); state = secrets.token_urlsafe(24)
        PENDING[state] = {"sid": sid, "verifier": verifier, "exp": now + 600}
        return RedirectResponse(BASE + "/auth/authorize?" + urlencode({"response_type": "code", "client_id": cid, "redirect_uri": REDIRECT,
            "code_challenge": b64(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256", "state": state, "scope": "mcp:tools"}))

    @r.get("/callback")
    async def callback(code: str = Query(..., max_length=2000), state: str = Query(..., max_length=200)):
        p = PENDING.pop(state, None)
        if not p or p["exp"] < time.time(): raise HTTPException(400, "Sign-in expired. Please start again.")
        try:
            x = await client.http().post(BASE + "/auth/token", json={"grant_type": "authorization_code", "code": code, "code_verifier": p["verifier"],
                                                                    "redirect_uri": REDIRECT, "client_id": CLIENT["id"]})
            x.raise_for_status(); d = x.json(); tok = d["access_token"]
        except Exception: raise HTTPException(502, "Swiggy sign-in failed. Please try again.")
        TOKENS[p["sid"]] = {"token": tok, "exp": time.time() + max(60, int(d.get("expires_in", 3600)) - 60)}
        return RedirectResponse(FRONTEND + "/?swiggy=connected")

    @r.get("/status")
    async def status(request: Request):
        sid = request.headers.get("x-session", ""); t = TOKENS.get(sid) if re.match(SID, sid) else None
        return {"logged_in": bool(t and t["exp"] > time.time())}

    @r.post("/logout")
    async def logout(request: Request):
        sid = request.headers.get("x-session", ""); t = TOKENS.pop(sid, None); client.mcp.pop(sid, None)
        if t:
            try: await client.http().post(BASE + "/auth/logout", headers={"Authorization": "Bearer " + t["token"]})
            except Exception: pass
        return {"logged_in": False}
    return r
