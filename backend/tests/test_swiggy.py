import sys, os, asyncio, json, time, base64, hashlib; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from urllib.parse import urlparse, parse_qs
import httpx, pytest, swiggy, engine
from fastapi import FastAPI
from fastapi.testclient import TestClient

SID = "sess-12345678"
def var(spin, sku, qd, price, ok=True, rating="4.6"):
    return {"spinId": spin, "skuId": sku, "quantityDescription": qd, "displayName": "Butter <b>x</b>", "brandName": "BrandX", "price": {"mrp": price + 4, "offerPrice": price},
            "isInStockAndAvailable": ok, "rating": {"value": rating, "count": "10"}}
SEARCH = {"success": True, "data": {"nextOffset": "1", "products": [{"displayName": "Butter", "brand": "BrandX", "inStock": True, "isAvail": True, "productId": "p1", "parentProductId": "pp",
          "variations": [var("S1", "K1", "100 g", 56), var("S2", "K2", "500 g", 250, ok=False), var("S3", "K3", "Assorted", 10)]}]}}
CART = {"success": True, "data": {"cartTotalAmount": "58", "selectedAddressDetails": {"id": "A1", "address": "x", "area": "y", "name": "Home", "mobile": "1"},
        "items": [{"spinId": "M1", "skuId": "MK1", "productId": "m", "itemName": "Milk", "itemVariant": "500 ml", "quantity": 2, "isInStockAndAvailable": True, "mrp": 30, "discountedFinalPrice": 29}],
        "billBreakdown": {"lineItems": [], "toPay": {"label": "", "value": ""}}}}

def fake(calls, sse=False):
    def handler(req):
        body = json.loads(req.content); calls.append((req.headers.get("authorization"), req.headers.get("mcp-session-id"), body)); m = body.get("method")
        if m == "initialize": return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26", "capabilities": {}}}, headers={"Mcp-Session-Id": "mcp-1"})
        if m == "notifications/initialized": return httpx.Response(202)
        env = {"get_addresses": {"success": True, "data": {"addresses": [{"id": "A1", "name": "Home", "area": "HSR"}]}}, "search_products": SEARCH, "get_cart": CART,
               "update_cart": {"success": True, "data": {"items": []}}}[body["params"]["name"]]
        res = {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": json.dumps(env)}]}}
        if sse: return httpx.Response(200, text="event: message\ndata: " + json.dumps(res) + "\n\n", headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json=res)
    return handler
def mk(sse=False, login=True):
    calls = []; c = swiggy.SwiggyInstamartMCPClient(transport=httpx.MockTransport(fake(calls, sse)))
    if login: swiggy.TOKENS[SID] = {"token": "tok", "exp": time.time() + 999}
    return c, calls
run = asyncio.run

def test_pack_parsing():
    assert swiggy.parse_pack("500 g") == (500, "g") and swiggy.parse_pack("1 L") == (1000, "ml") and swiggy.parse_pack("2 x 100 g") == (200, "g")
    assert swiggy.parse_pack("Pack of 6") == (6, "piece") and swiggy.parse_pack("250 ml") == (250, "ml") and swiggy.parse_pack("Assorted") is None
@pytest.mark.parametrize("sse", [False, True])
def test_search_maps_real_schema_json_and_sse(sse):
    c, calls = mk(sse); ps = run(c.search("butter", "A1", SID))
    assert [p["product_id"] for p in ps] == ["S1", "S2", "S3"] and ps[0]["price"] == 56 and (ps[0]["pack_quantity"], ps[0]["pack_unit"]) == (100, "g")
    assert ps[0]["availability"] and not ps[1]["availability"] and ps[0]["rating"] == 4.6 and "<" not in ps[0]["name"] and ps[2]["pack_quantity"] is None
    assert calls[0][2]["method"] == "initialize" and all(c_[0] == "Bearer tok" for c_ in calls) and calls[-1][1] == "mcp-1"
    assert calls[-1][2]["params"] == {"name": "search_products", "arguments": {"addressId": "A1", "query": "butter"}}
def test_engine_uses_swiggy_products_unmodified():
    c, _ = mk(); ps = run(c.search("butter", "A1", SID))
    req = {"requirement_id": "r1", "ingredient_name": "butter", "normalized_name": "butter", "required_quantity": 30, "unit": "g", "category": None, "optional": False, "notes": None}
    r = engine.solve(req, ps); assert r["selection"][0]["product"] == ps[0] and r["selection"][0]["packs"] == 1 and [u["product"]["product_id"] for u in r["unavailable"]] == ["S2"]
def test_update_cart_replaces_so_we_send_existing_plus_new_with_sku():
    c, calls = mk(); run(c.search("butter", "A1", SID)); before = run(c.get_cart(SID))
    merged = engine.merge_cart(before, [{"product_id": "S1", "name": "Butter", "packs": 1, "price": 56}]); run(c.update_cart(SID, merged))
    args = [x[2]["params"] for x in calls if x[2].get("params", {}).get("name") == "update_cart"][0]["arguments"]
    assert args == {"selectedAddressId": "A1", "items": [{"spinId": "M1", "skuId": "MK1", "quantity": 2}, {"spinId": "S1", "skuId": "K1", "quantity": 1}]}
def test_only_allowlisted_tools_checkout_and_payment_blocked():
    c, _ = mk()
    for t in ("checkout", "confirm_order", "get_payment_options", "delete_address"):
        with pytest.raises(PermissionError): run(c.call(SID, t, {}, confirmed=True))
    with pytest.raises(PermissionError): run(c.call(SID, "update_cart", {}))
    with pytest.raises(PermissionError): run(c.call(SID, "clear_cart", {}))  # mutating: needs explicit confirmation
    with pytest.raises(swiggy.SwiggyError): run(c.update_cart(SID, [{"product_id": "ghost", "packs": 1}], "A1"))
def test_not_logged_in_and_expired_session():
    swiggy.TOKENS.pop("nologin-1234", None); c, _ = mk(login=False)
    with pytest.raises(swiggy.NeedLogin): run(c.get_cart("nologin-1234"))
    swiggy.TOKENS[SID] = {"token": "t", "exp": time.time() - 1}
    with pytest.raises(swiggy.NeedLogin): run(c.addresses(SID))
def test_oauth_pkce_login_and_callback():
    seen = {"reg": 0}
    def h(req):
        if req.url.path == "/auth/register": seen["reg"] += 1; return httpx.Response(201, json={"client_id": "cid-1"})
        if req.url.path == "/auth/token": seen["tok"] = json.loads(req.content); return httpx.Response(200, json={"access_token": "AT", "expires_in": 432000})
        return httpx.Response(404)
    c = swiggy.SwiggyInstamartMCPClient(transport=httpx.MockTransport(h)); swiggy.CLIENT["id"] = None; app = FastAPI(); app.include_router(swiggy.make_router(c))
    t = TestClient(app, follow_redirects=False); sid = "abcdefgh-1"
    tk = t.post("/api/swiggy/login-start", headers={"X-Session": sid}).json()["ticket"]
    loc = t.get("/api/swiggy/login", params={"ticket": tk}).headers["location"]; q = {k: v[0] for k, v in parse_qs(urlparse(loc).query).items()}
    assert loc.startswith("https://mcp.swiggy.com/auth/authorize?") and q["code_challenge_method"] == "S256" and q["client_id"] == "cid-1" and q["scope"] == "mcp:tools" and q["redirect_uri"] == swiggy.REDIRECT
    done = t.get("/api/swiggy/callback", params={"code": "CODE", "state": q["state"]}); assert done.status_code in (302, 307) and done.headers["location"].startswith(swiggy.FRONTEND)
    ver = seen["tok"]["code_verifier"]; assert base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode() == q["code_challenge"]
    assert seen["tok"]["grant_type"] == "authorization_code" and seen["tok"]["redirect_uri"] == swiggy.REDIRECT and swiggy.TOKENS[sid]["token"] == "AT"
    assert t.get("/api/swiggy/status", headers={"X-Session": sid}).json() == {"logged_in": True} and t.get("/api/swiggy/status", headers={"X-Session": "other-1234"}).json() == {"logged_in": False}
    t.get("/api/swiggy/login", params={"ticket": t.post("/api/swiggy/login-start", headers={"X-Session": sid}).json()["ticket"]}); assert seen["reg"] == 1  # client registered once
    assert t.get("/api/swiggy/callback", params={"code": "X", "state": q["state"]}).status_code == 400  # state is single-use
    assert t.get("/api/swiggy/login", params={"ticket": tk}).status_code == 400            # a ticket works once
    assert t.get("/api/swiggy/login", params={"sid": "attacker-chosen-sid"}).status_code == 422  # a link can no longer choose which session gets logged in
    assert t.post("/api/swiggy/login-start", headers={"X-Session": "bad sid!"}).status_code == 400

def test_order_mode_is_false_and_cannot_be_enabled():
    import main, subprocess
    assert TestClient(main.app).get("/api/health").json()["order_mode"] is False
    r = subprocess.run([sys.executable, "-c", "import main"], cwd=os.path.dirname(os.path.dirname(__file__)), env={**os.environ, "ALLOW_REAL_ORDER_PLACEMENT": "true"}, capture_output=True, text=True)
    assert r.returncode != 0 and "ALLOW_REAL_ORDER_PLACEMENT must be false" in r.stderr


def test_refuses_to_replace_a_cart_it_cannot_fully_read(monkeypatch):
    import copy
    bad = copy.deepcopy(CART); bad["data"]["items"].append({"itemName": "Mystery", "quantity": 1})
    monkeypatch.setitem(globals(), "CART", bad)
    c, _ = mk()
    with pytest.raises(swiggy.SwiggyError, match="won't touch the cart"): run(c.get_cart(SID))

def test_only_the_tools_this_app_uses_are_reachable():
    assert swiggy.READ == {"get_addresses", "search_products", "get_cart"} and swiggy.CONFIRM == {"update_cart", "clear_cart", "create_address"}
    js = open(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "app.js"), encoding="utf-8").read()
    assert "sid=" not in js.split("login-start")[1][:200]  # the session handle never goes into a URL
