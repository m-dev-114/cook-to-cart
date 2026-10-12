import asyncio, hashlib, json, os, re, time
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import engine, extract, intent, llm, retrieval, swiggy, understand, visual
from instamart import make_client

if os.getenv("ALLOW_REAL_ORDER_PLACEMENT", "false").strip().lower() != "false": raise RuntimeError("ALLOW_REAL_ORDER_PLACEMENT must be false: this project never places real orders.")
MODE = os.getenv("INSTAMART_MODE", "swiggy")  # live Swiggy is the normal mode; "local" is an explicit, clearly labelled demo catalog
if MODE not in ("local", "swiggy"): raise RuntimeError("INSTAMART_MODE must be 'local' or 'swiggy'")
ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
if "*" in ORIGINS: raise RuntimeError("ALLOWED_ORIGINS must not contain '*'")
LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
client = make_client(MODE)
if MODE == 'swiggy': pass
print('features:', {'groq': bool(llm.KEY), 'gemini_visual': visual.ENABLED})  # never log keys
app = FastAPI(title="Recipe-Video to Cart", docs_url=None, redoc_url=None, openapi_url=None)
HITS, DONE, ADDR = defaultdict(deque), {}, {}  # ADDR: session -> delivery address chosen (and validated) server-side
if MODE == "swiggy": app.include_router(swiggy.make_router(client))


@app.middleware("http")
async def guard(request: Request, call_next):
    xf = request.headers.get("x-forwarded-for", "").split(",")[-1].strip()
    ip = xf or (request.client.host if request.client else "?")
    now = time.time(); q = HITS[ip]
    while q and now - q[0] > 60: q.popleft()
    if len(q) >= LIMIT: return JSONResponse({"detail": "Rate limit exceeded, try again shortly."}, 429)
    q.append(now)
    if len(HITS) > 10000: HITS.clear()
    if int(request.headers.get("content-length") or 0) > 200_000: return JSONResponse({"detail": "Body too large"}, 413)
    try: r = await call_next(request)
    except Exception as e:
        import traceback; print("unhandled", type(e).__name__, "".join(traceback.format_exception(e)[-4:])[-900:]); return JSONResponse({"detail": "Internal error"}, 500)
    r.headers.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
                      "Strict-Transport-Security": "max-age=63072000", "Content-Security-Policy": "default-src 'none'"})
    return r

app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Session"])


class Ing(BaseModel):
    name: str = Field(max_length=200); quantity: float | None = Field(None, ge=0, le=100000)
    unit: str | None = Field(None, max_length=20); optional: bool = False
    size: str | None = Field(None, max_length=20); canonical_name: str | None = Field(None, max_length=200); quantity_confidence: str | None = Field(None, max_length=12)
    preparation: str | None = Field(None, max_length=60); raw_text: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=300); normalized_name: str | None = Field(None, max_length=200)
    source_quantity: float | None = Field(None, ge=0, le=100000); source_unit: str | None = Field(None, max_length=20)
    source_text: str | None = Field(None, max_length=60); normalized_is_estimate: bool | None = None; est_piece_g: float | None = Field(None, ge=0, le=5000)
    confidence: str | None = Field(None, max_length=12); seen_at: str | None = Field(None, max_length=10); conflict: str | None = Field(None, max_length=160)

class Req(BaseModel):
    source_text: str | None = Field(None, max_length=60); est_piece_g: float | None = Field(None, ge=0, le=5000); normalized_is_estimate: bool = False
    requirement_id: str = Field(max_length=20); ingredient_name: str = Field(max_length=200)
    normalized_name: str = Field(max_length=200); required_quantity: float | None = Field(None, ge=0, le=100000)
    unit: str | None = Field(None, max_length=20); category: str | None = None; optional: bool = False; notes: str | None = None; interp: dict | None = None

class ExtractIn(BaseModel):
    input: str | None = Field(None, max_length=20000)
    url: str | None = Field(None, max_length=2048); text: str | None = Field(None, max_length=20000)
class NormIn(BaseModel): lines: list[str] = Field(max_length=80)
class ScaleIn(BaseModel):
    ingredients: list[Ing] = Field(max_length=80); from_servings: float = Field(gt=0, le=100); to_servings: float = Field(gt=0, le=100)
class PantryIn(BaseModel): name: str = Field(max_length=100); quantity: float | None = Field(None, ge=0, le=100000); unit: str | None = Field(None, max_length=20)
class HaveIn(BaseModel): name: str = Field(max_length=100); status: str = Field(pattern="^(full|unknown)$")
class NewAddr(BaseModel):
    confirm: bool = False; fullAddress: str = Field(min_length=5, max_length=300); addressLine: str = Field(min_length=2, max_length=200); addressLine2: str = Field("", max_length=100)
    locality: str | None = Field(None, max_length=100); city: str = Field(min_length=2, max_length=80); postalCode: str = Field(pattern=r"^[0-9A-Za-z \-]{3,10}$")
    addressCategory: str = Field(pattern="^(HOME|WORK|OFFICE|FRIENDS_AND_FAMILY|OTHER)$"); addressTag: str | None = Field(None, max_length=40)
    userName: str = Field(min_length=1, max_length=80); userPhone: str = Field(pattern=r"^\+?[0-9]{7,15}$")
class AddrIn(BaseModel): address_id: str = Field(max_length=100)
class ReqIn(BaseModel):
    ingredients: list[Ing] = Field(max_length=80); pantry: dict[str, str] = {}; pantry_items: list[PantryIn] = Field([], max_length=60)
class MatchIn(BaseModel): requirements: list[Req] = Field(max_length=60); address_id: str | None = Field(None, max_length=100)
class OptIn(MatchIn):
    overrides: dict[str, str] = {}; pack_counts: dict[str, int] = {}; approved_substitutes: list[str] = []; have: list[HaveIn] = Field([], max_length=80); skipped: list[str] = Field([], max_length=80)
    budget: float | None = Field(None, ge=0, le=10000000); mode: str = Field("best", pattern="^(best|cheapest|least_excess)$")
class CartItem(BaseModel): product_id: str = Field(max_length=100); packs: int = Field(ge=1, le=20); source: str | None = Field(None, max_length=120)
class CartIn(BaseModel):
    items: list[CartItem] = Field(max_length=60); confirm: bool = False
    expected_cart_hash: str = Field(max_length=64); idempotency_key: str = Field(min_length=8, max_length=64); address_id: str | None = Field(None, max_length=100)
    budget: float | None = Field(None, ge=0, le=10000000); allow_over_budget: bool = False


def sid(r: Request): return re.sub(r"[^A-Za-z0-9-]", "", r.headers.get("x-session", "demo"))[:64] or "demo"
def chash(cart):  # fingerprint of WHAT is in the cart (product + quantity); prices/names change between reads and must not invalidate a review
    return hashlib.sha256(json.dumps(sorted([i["product_id"], i["packs"]] for i in cart)).encode()).hexdigest()[:32]


@app.exception_handler(swiggy.NeedLogin)
async def _nl(_, e): return JSONResponse({"detail": "Connect your Swiggy account to continue.", "login_required": True}, 401)


@app.exception_handler(swiggy.SwiggyError)
async def _se(_, e):
    print("swiggy error:", getattr(e, "kind", "?"))  # kind only: never log payloads or tokens
    return JSONResponse({"detail": str(e)[:200], "kind": getattr(e, "kind", None)}, 429 if getattr(e, "kind", "") == "MCP_RATE_LIMITED" else 502)


@app.exception_handler(extract.ExtractError)
async def _ee(_, e): return JSONResponse({"detail": str(e)}, 422)


@app.post("/api/place-order")
async def place_order(): raise HTTPException(403, "Real order placement is disabled in this project.")  # fails closed whatever the client sends


@app.get("/api/health")
async def health(): return {"ok": True, "mode": MODE, "label": client.label, "order_mode": False}


def detect(s):
    s = s.strip()
    if re.fullmatch(r"(?:https?://|www\.|(?:m\.)?youtu(?:\.be|be\.com)/)\S+", s, re.I): return "url"
    ls = [l for l in s.splitlines() if l.strip()]
    return "text" if sum(1 for l in ls if re.match(r"^\W*[\d¼½¾⅓⅔]", l)) >= 2 or len(ls) >= 4 else "dish"


async def _dish(s):
    it = intent.parse_intent(s); sv = it["servings"] or 4; s = it["dish"]
    if len(s) < 2: raise HTTPException(400, "Type a dish, paste a recipe, or paste a link.")
    if not llm.KEY: raise extract.ExtractError("Typing a dish name needs the AI step (no GROQ_API_KEY on the server). Paste a recipe or a link instead.")
    try: rec = await llm.generate_recipe(s, sv)
    except Exception as ex:
        r = getattr(ex, "response", None); print("dish llm error:", type(ex).__name__, getattr(r, "status_code", None), (getattr(r, "text", "") or "")[:200]); rec = None
    if not rec: raise extract.ExtractError("Couldn't generate a recipe for that dish. Try again, or paste the recipe.")
    items = [{"line": f'{i["quantity"]} {i["name"]}' if i["quantity"] else i["name"], "confidence": "estimated", "seen_at": None, "conflict": None} for i in rec["ingredients"]]
    return {"title": rec["title"] or s.title(), "servings": sv, "items": items, "steps": rec["steps"], "partial": False, "source": "AI-generated from dish name", "pantry": it["pantry"], "budget": it["budget"],
            "warning": f"AI-generated typical recipe for {sv} servings, not from a specific source. Check quantities."}


@app.post("/api/extract")
async def do_extract(b: ExtractIn, request: Request):
    url, text, dish = b.url, b.text, None
    if b.input and b.input.strip():  # ONE input: dish name, recipe text, recipe URL or video URL
        s = b.input.strip(); k = detect(s)
        if k == "url": url = s if re.match(r"https?://", s, re.I) else "https://" + s
        elif k == "text": text = s
        else: dish = s
    if url:
        ip = request.headers.get('x-forwarded-for', '').split(',')[-1].strip() or (request.client.host if request.client else '?')
        r = await extract.from_url(url.strip(), ip)
    elif text and text.strip():
        ls = [l.strip() for l in text.splitlines() if l.strip()][:80]
        title = "Pasted recipe"
        if ls and not ls[0][0].isdigit() and len(ls) > 1: title = ls.pop(0)[:150]
        sv = re.search(r"serves?\s*(\d+)", text, re.I)
        r = {"title": title, "servings": int(sv.group(1)) if sv else 4, "lines": [l for l in ls if not re.match(r"\W*ingredients\W*$", l, re.I)], "source": "pasted text"}
    elif dish: r = await _dish(dish)
    else: raise HTTPException(400, "Type a dish, paste a recipe, or paste a link.")
    if r.get("items"):  # visual / dish path: keep per-ingredient confidence / timestamp / conflict
        ings = []
        for it in r["items"]:
            p = engine.parse_line(it["line"])
            if p: p.update({k: it.get(k) for k in ("confidence", "seen_at", "conflict")}); ings.append(p)
    else: ings = [i for i in map(engine.parse_line, r["lines"]) if i]
    if not ings: raise extract.ExtractError("No ingredients could be parsed. Please paste the recipe text.")
    return {"title": r["title"], "servings": max(1, r["servings"]), "source": r["source"], "warning": r.get("warning"), "steps": r.get("steps"),
            "visual": r.get("visual"), "partial": r.get("partial"), "pantry": r.get("pantry"), "budget": r.get("budget"), "ingredients": engine.consolidate(ings),
            "suggested_missing": engine.missing_essentials(r["title"], ings)}


@app.post("/api/normalize")
async def normalize(b: NormIn): return {"ingredients": [i for i in map(engine.parse_line, b.lines) if i]}


@app.post("/api/scale")
async def scale(b: ScaleIn): return {"ingredients": engine.scale_ings([i.model_dump() for i in b.ingredients], b.from_servings, b.to_servings)}


@app.post("/api/shopping-requirements")
async def reqs(b: ReqIn):
    if any(v not in ("have", "buy", "skip") for v in b.pantry.values()): raise HTTPException(400, "Invalid pantry status")
    ings = [i.model_dump() for i in b.ingredients]
    rq, have = engine.apply_pantry(engine.make_requirements(ings, b.pantry), [p.model_dump() for p in b.pantry_items])
    have += [{"name": i["name"], "status": "full"} for i in ings if b.pantry.get(i["name"]) == "have" or (engine.FREE_WATER.match((i.get("normalized_name") or i["name"]).lower().strip()) and b.pantry.get(i["name"], "buy") == "buy")]
    skipped = [i["name"] for i in ings if b.pantry.get(i["name"]) == "skip" and not i.get("optional")]  # includes "as needed / to taste" lines: they are not bought, and are reported as skipped
    byn = {i["name"]: i for i in ings}; need = [byn[r["ingredient_name"]] for r in rq if r["ingredient_name"] in byn]
    for r, p in zip([r for r in rq if r["ingredient_name"] in byn], await understand.interpret(need)): r["interp"] = understand.for_requirement(p)  # Stage A: hints only
    return {"requirements": rq, "have": have, "skipped": skipped}


@app.get("/api/instamart/addresses")
async def addresses(request: Request):
    s = sid(request); ad = await client.addresses(s)
    return {"addresses": ad, "selected": ADDR.get(s) if ADDR.get(s) in {a["id"] for a in ad} else None, "label": client.label}


@app.post("/api/instamart/address")
async def pick_address(b: AddrIn, request: Request):
    s = sid(request)
    if b.address_id not in {a["id"] for a in await client.addresses(s)}: raise HTTPException(403, "That address isn't available on your account.")  # never trust a client-supplied id
    if len(ADDR) > 5000: ADDR.clear()
    ADDR[s] = b.address_id; return {"address_id": b.address_id}


@app.post("/api/instamart/address/create")
async def new_address(b: NewAddr, request: Request):
    if not b.confirm: raise HTTPException(400, "Explicit confirmation required.")
    if not hasattr(client, "create_address"): raise HTTPException(501, "Adding an address is only available with a connected Swiggy account.")
    s = sid(request); body = {k: v for k, v in b.model_dump().items() if k != "confirm" and v not in (None,)}
    aid = await client.create_address(s, body)
    ad = await client.addresses(s)  # never trust the create response alone: the address must appear in the account's list
    if aid not in {a["id"] for a in ad}: raise HTTPException(502, "Swiggy accepted the address but it isn't in your address list yet. Reload and check.")
    ADDR[s] = aid; return {"address_id": aid, "addresses": ad}


@app.get("/api/instamart/products")
async def products(request: Request, q: str = Query("", max_length=100), address_id: str | None = Query(None, max_length=100)):
    return {"products": await retrieval.manual_search(client, q, address_id, sid(request)), "label": client.label}


@app.get("/api/instamart/cart")
async def cart(request: Request):
    s = sid(request); c = await client.get_cart(s); return {"items": c, "hash": chash(c), "cart_total": getattr(client, "totals", {}).get(s), "bill": getattr(client, "bills", {}).get(s), "label": client.label}


async def _solve(b: OptIn, s=None):
    addr = ADDR.get(s) or (None if MODE == "swiggy" else b.address_id)
    if MODE == "swiggy" and not addr: raise HTTPException(409, "Choose your delivery address first.")  # no product search before a delivery address
    found = await asyncio.gather(*[_search_req(r.model_dump(), addr, s) for r in b.requirements])
    if found and all(e is not None for _, e in found): raise found[0][1]  # the whole search is down: report it (429 / 502), don't pretend every item is unavailable
    out = []
    for r, (ps, errs) in zip(b.requirements, found):
        if errs is not None and not ps: out.append(engine.failed_result(r.model_dump())); continue  # every search errored: that is NOT "unavailable"
        try: out.append(engine.solve(r.model_dump(), ps, r.requirement_id in b.approved_substitutes, b.overrides.get(r.requirement_id), max(1, min(20, b.pack_counts[r.requirement_id])) if r.requirement_id in b.pack_counts else None, b.mode))
        except ValueError as e: raise HTTPException(400, str(e))
    return out


async def _search_req(rd, addr, s): return await retrieval.retrieve(client, rd, addr, s)


@app.post("/api/match-products")
async def match(b: MatchIn, request: Request):
    res = await _solve(OptIn(**b.model_dump()), sid(request))
    return {"matches": [{"requirement_id": x["requirement"]["requirement_id"], "candidates": x["candidates"]} for x in res], "label": client.label}


@app.post("/api/optimize-cart")
async def optimize(b: OptIn, request: Request):
    items = await _solve(b, sid(request))
    total = round(sum(l["line_total"] for x in items for l in x["selection"]), 2)
    return {"items": items, "estimated_total": total, "label": client.label, "coverage": engine.coverage(items, [h.model_dump() for h in b.have], b.skipped),
            "budget": None if b.budget is None else {"limit": b.budget, "over_by": round(max(0, total - b.budget), 2)}}


OPS = {}  # "session:operation" -> {before, desired, state, extra}  (one logical cart operation = one mutation, ever)
MSG = {"CONFIRMED": "Cart synced.", "PARTIAL": "Some changes were applied but the live cart doesn't match what we asked for. Please review it.",
       "NOT_APPLIED": "Nothing was changed in your cart.", "UNKNOWN": "We couldn't confirm the cart update. Please review the live cart before trying again."}


class ClearIn(BaseModel): confirm: bool = False; idempotency_key: str = Field(min_length=8, max_length=64)


def _body(status, key, after, extra=None):
    view = None if after is None else [{"product_id": i["product_id"], "name": i["name"], "packs": i["packs"], "price": i.get("price"), "source_ingredient": i.get("source_ingredient")} for i in after]
    return {"status": status, "operation_id": key, "message": (extra or {}).get("message_override") or ((extra or {}).get("ok_message") if status == "CONFIRMED" else None) or MSG[status], "cart": view, "after": view or [], "hash": None if after is None else chash(after),
            "verification": {"verified": status == "CONFIRMED"}, "verified": status == "CONFIRMED", "label": client.label, **(extra or {})}


async def _verify(s, before, desired):
    """The live Swiggy cart is authoritative: fetch it and compare. A transport error never decides the outcome."""
    try: after = await client.get_cart(s)
    except Exception as e:
        print("verify failed:", getattr(e, "kind", type(e).__name__)); return "UNKNOWN", None
    return engine.reconcile(before, desired, after), after


def _diag(desired, after, wanted_addr=None, cart_addr=None):
    """What we asked for vs what the live cart really holds, so an empty/mismatched cart is explained instead of hidden."""
    got = {i["product_id"]: i["packs"] for i in (after or [])}
    missing = [{"product_id": i["product_id"], "name": i.get("name"), "wanted": i["packs"], "found": got.get(i["product_id"], 0)} for i in desired if got.get(i["product_id"], 0) < i["packs"]]
    d = {"wanted_items": len(desired), "live_items": len(got), "missing": missing}
    if wanted_addr and cart_addr and wanted_addr != cart_addr: d["address_mismatch"] = True
    return d


INFLIGHT = set()  # sessions with a cart mutation running: a second click/tab can never start a parallel mutation


@app.post("/api/instamart/cart")
async def add_cart(b: CartIn, request: Request):
    if not b.confirm: raise HTTPException(400, "Explicit user confirmation required.")
    s = sid(request)
    if s in INFLIGHT: return JSONResponse({"detail": "A cart update is already in progress. Wait for it to finish; nothing was changed by this request.", "code": "IN_PROGRESS", "status": "FAILED_BEFORE_MUTATION"}, 409)
    INFLIGHT.add(s)
    try: return await _add_cart(b, request)
    finally: INFLIGHT.discard(s)


async def _add_cart(b, request):
    s = sid(request); key = f"{s}:{b.idempotency_key}"; op = OPS.get(key)
    if op:  # same logical operation again: NEVER mutate twice, only re-check the live cart
        status, after = await _verify(s, op["before"], op["desired"]); op["state"] = status
        return JSONResponse(_body(status, b.idempotency_key, after, op["extra"]), 202 if status == "UNKNOWN" else 200)
    before = await client.get_cart(s)  # failures here are FAILED_BEFORE_MUTATION: nothing was sent
    if chash(before) != b.expected_cart_hash: return JSONResponse({"detail": "Your Instamart cart changed since you reviewed it. The review was refreshed; check it and press Add again. Nothing was changed.", "code": "CART_CHANGED", "hash": chash(before), "status": "FAILED_BEFORE_MUTATION"}, 409)
    addr = ADDR.get(s) or (None if MODE == "swiggy" else b.address_id)
    if MODE == "swiggy" and not addr: raise HTTPException(409, "Choose your delivery address first.")
    agg, src, new, pchanges = {}, {}, [], []
    for it in b.items: agg[it.product_id] = agg.get(it.product_id, 0) + it.packs; src.setdefault(it.product_id, re.sub(r"[<>]", "", it.source or "")[:120] or None)
    for pid, n in agg.items():
        k = await client.known(pid, s)
        if not k or n > 20: raise HTTPException(400, f"Product {pid[:30]} is unknown or over the pack limit.")
        p = await client.revalidate(pid, s, addr)  # live re-check before touching the cart
        if not p or not p["availability"]: raise HTTPException(409, f'"{k["name"][:60]}" is no longer available. Go back and choose another product; nothing was added.')
        if k.get("price") is not None and p.get("price") is not None and abs(p["price"] - k["price"]) > 0.005: pchanges.append({"name": p["name"][:60], "was": k["price"], "now": p["price"]})
        new.append({"product_id": p["product_id"], "name": f'{p["name"]} ({p.get("brand") or ""}, {p.get("pack_label") or (format(p["pack_quantity"], "g") + " " + p["pack_unit"] if p.get("pack_quantity") else "")})',
                    "packs": n, "price": p["price"], "source_ingredient": src.get(pid)})
    if pchanges:  # a live price moved since the user chose: never silently use either price, ask again
        return JSONResponse({"detail": "Price updated: " + "; ".join(f'{c["name"]} was ₹{c["was"]:g}, now ₹{c["now"]:g}' for c in pchanges[:5]) + ". Please review before continuing. Nothing was added.",
                             "status": "FAILED_BEFORE_MUTATION", "price_changes": pchanges}, 409)
    total = round(sum(i["price"] * i["packs"] for i in new), 2)
    if b.budget is not None and total > b.budget + 1e-6 and not b.allow_over_budget: raise HTTPException(409, f"Over your budget by ₹{total - b.budget:.2f}. Nothing was added.")
    desired, changes = engine.plan_cart(before, new)
    extra = {"total": total, "changes": changes, "price_changes": pchanges, "operation": "add", "no_change": not changes,
             "ok_message": "No update was necessary: these items were already in your Instamart cart at the needed quantity (verified against the live cart). No checkout or payment was made." if not changes else "Instamart cart verified: the live cart contains these items. No checkout or payment was made."}
    if len(OPS) > 2000: OPS.clear()
    if not changes:  # everything is already in the live cart at the needed quantity
        OPS[key] = {"before": before, "desired": desired, "state": "CONFIRMED", "extra": extra}; return JSONResponse(_body("CONFIRMED", b.idempotency_key, before, extra))
    OPS[key] = {"before": before, "desired": desired, "state": "MUTATION_ATTEMPTED", "extra": extra}
    err = None
    try: await client.update_cart(s, desired, addr)
    except swiggy.NeedLogin: OPS.pop(key, None); raise  # rejected before anything was applied
    except Exception as e: err = e; print("cart mutation error:", getattr(e, "kind", type(e).__name__))  # may still have been applied: DO NOT retry, verify
    status, after = await _verify(s, before, desired); OPS[key]["state"] = status
    bill = getattr(client, "bills", {}).get(s)
    adj = getattr(client, "adjust", {}).pop(s, None)
    if adj and (adj["removed"] or adj["reduced"]): extra["adjustments"] = adj
    try: extra["delivery_address"] = next((a["label"] for a in await client.addresses(s) if a["id"] == addr), None)
    except Exception: extra["delivery_address"] = None  # label is informational only
    extra["cart_address_matches"] = None if not getattr(client, "cart_addr", {}).get(s) or not addr else client.cart_addr[s] == addr
    if bill: extra["bill"] = bill
    if bill and b.budget is not None and bill.get("to_pay_amount") is not None and bill["to_pay_amount"] > b.budget + 1e-6: extra["budget_warning"] = f"The live cart total to pay (₹{bill['to_pay_amount']:g}, including any fees Swiggy lists) is over your ₹{b.budget:g} budget."
    dg = None if status == "CONFIRMED" else _diag(desired, after, addr, getattr(client, "cart_addr", {}).get(s))
    if status == "NOT_APPLIED" and after is not None: extra["message_override"] = ("Instamart returned an empty cart" if not after else "The live cart did not change") + " after the update, so the items were NOT confirmed in your cart."
    if dg and dg.get("address_mismatch"): extra["message_override"] = "The live cart belongs to a different delivery address than the one selected here. Nothing was verified."
    return JSONResponse(_body(status, b.idempotency_key, after, {**extra, "diagnostic": dg, "mutation_error": None if err is None else getattr(err, "kind", "ERROR")}), 202 if status == "UNKNOWN" else 200)


@app.post("/api/instamart/cart/clear")
async def clear_cart(b: ClearIn, request: Request):
    if not b.confirm: raise HTTPException(400, "Explicit confirmation required.")
    s = sid(request)
    if s in INFLIGHT: return JSONResponse({"detail": "A cart update is already in progress. Wait for it to finish; nothing was changed by this request.", "code": "IN_PROGRESS", "status": "FAILED_BEFORE_MUTATION"}, 409)
    INFLIGHT.add(s)
    try: return await _clear_cart(b, s)
    finally: INFLIGHT.discard(s)


async def _clear_cart(b, s):
    before = await client.get_cart(s); err = None
    try: await client.clear_cart(s)
    except swiggy.NeedLogin: raise
    except Exception as e: err = e; print("clear error:", getattr(e, "kind", type(e).__name__))
    try: after = await client.get_cart(s)
    except Exception: after = None
    status = "UNKNOWN" if after is None else ("CONFIRMED" if not after else ("NOT_APPLIED" if len(after) == len(before) else "PARTIAL"))
    return JSONResponse(_body(status, b.idempotency_key, after, {"operation": "clear", "ok_message": "Instamart cart cleared and verified: the live cart is now empty. Nothing was checked out or paid.", "mutation_error": None if err is None else getattr(err, "kind", "ERROR")}), 202 if status == "UNKNOWN" else 200)
