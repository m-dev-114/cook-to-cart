import sys, os, asyncio, json, time; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import httpx, pytest, engine as e, main, swiggy, test_swiggy as ts
from fastapi.testclient import TestClient

def P(i, q, price, u="g", name="Rice", av=True):
    return dict(product_id=i, name=name, brand="B", category=None, variant=None, pack_quantity=q, pack_unit=u, price=price, availability=av, image_url=None)
def R(n, q=300, u="g"): return dict(requirement_id="r1", ingredient_name=n, normalized_name=n, required_quantity=q, unit=u, category=None, optional=False, notes=None)

def post(c, items, key, **k):
    h = c.get("/api/instamart/cart").json()["hash"]
    return c.post("/api/instamart/cart", json={"items": items, "confirm": True, "expected_cart_hash": h, "idempotency_key": key, **k})
ITEM = [{"product_id": "may-a1", "packs": 1}]
def ids(c): return {i["product_id"]: i["packs"] for i in c.get("/api/instamart/cart").json()["items"]}

def test_mutation_applied_but_response_failed_is_confirmed_and_never_retried(monkeypatch):
    real, calls = main.client.update_cart, []
    async def flaky(sid, items, address_id=None): calls.append(1); await real(sid, items, address_id); raise swiggy.SwiggyError("502 after success", "MCP_UPSTREAM_ERROR")
    monkeypatch.setattr(main.client, "update_cart", flaky); c = TestClient(main.app, headers={"X-Session": "ops-confirm-1"})
    r = post(c, ITEM, "op-confirm-key1"); d = r.json()
    assert r.status_code == 200 and d["status"] == "CONFIRMED" and d["mutation_error"] == "MCP_UPSTREAM_ERROR" and len(calls) == 1 and ids(c)["may-a1"] == 1
    again = c.post("/api/instamart/cart", json={"items": ITEM, "confirm": True, "expected_cart_hash": "stale", "idempotency_key": "op-confirm-key1"}).json()
    assert again["status"] == "CONFIRMED" and len(calls) == 1  # same operation: re-verified, not re-sent
def test_failed_without_applying_is_not_applied_and_cart_untouched(monkeypatch):
    async def dead(sid, items, address_id=None): raise swiggy.SwiggyError("timeout", "MCP_TIMEOUT")
    monkeypatch.setattr(main.client, "update_cart", dead); c = TestClient(main.app, headers={"X-Session": "ops-none-0001"})
    d = post(c, ITEM, "op-none-key01").json(); assert d["status"] == "NOT_APPLIED" and d["mutation_error"] == "MCP_TIMEOUT" and "may-a1" not in ids(c)
def test_partial_mutation_is_reported_partial(monkeypatch):
    real = main.client.update_cart
    async def half(sid, items, address_id=None): await real(sid, items[:-1], address_id)
    monkeypatch.setattr(main.client, "update_cart", half); c = TestClient(main.app, headers={"X-Session": "ops-part-0001"})
    d = post(c, [{"product_id": "may-a1", "packs": 1}, {"product_id": "hon-a1", "packs": 1}], "op-part-key001").json()
    assert d["status"] == "PARTIAL" and d["verification"]["verified"] is False and "hon-a1" not in ids(c)
def test_unknown_when_live_cart_cannot_be_read_then_retry_reverifies_without_remutating(monkeypatch):
    st, calls, real_get = {"armed": False}, [], main.client.get_cart
    async def upd(sid, items, address_id=None): calls.append(1); st["armed"] = True; raise swiggy.SwiggyError("lost", "MCP_TIMEOUT")
    async def get(sid):
        if st["armed"]: raise swiggy.SwiggyError("down", "MCP_UPSTREAM_ERROR")
        return await real_get(sid)
    monkeypatch.setattr(main.client, "update_cart", upd); monkeypatch.setattr(main.client, "get_cart", get); c = TestClient(main.app, headers={"X-Session": "ops-unk-00001"})
    h = c.get("/api/instamart/cart").json()["hash"]
    r = c.post("/api/instamart/cart", json={"items": ITEM, "confirm": True, "expected_cart_hash": h, "idempotency_key": "op-unk-key0001"})
    assert r.status_code == 202 and r.json()["status"] == "UNKNOWN" and r.json()["cart"] is None
    st["armed"] = False
    r2 = c.post("/api/instamart/cart", json={"items": ITEM, "confirm": True, "expected_cart_hash": h, "idempotency_key": "op-unk-key0001"})
    assert r2.json()["status"] == "NOT_APPLIED" and len(calls) == 1  # verified against the live cart; no blind retry
def test_no_duplicate_when_already_in_cart():
    c = TestClient(main.app, headers={"X-Session": "ops-dup-00001"})
    assert post(c, ITEM, "op-dup-key00001").json()["status"] == "CONFIRMED" and ids(c)["may-a1"] == 1
    d = post(c, ITEM, "op-dup-key00002").json(); assert d["status"] == "CONFIRMED" and d["changes"] == [] and ids(c)["may-a1"] == 1
    d = post(c, [{"product_id": "may-a1", "packs": 2}], "op-dup-key00003").json(); assert ids(c)["may-a1"] == 2 and d["changes"] == [{"product_id": "may-a1", "from": 1, "to": 2}]
def test_clear_cart_requires_confirmation_verifies_and_keeps_recipe_state():
    c = TestClient(main.app, headers={"X-Session": "ops-clear-001"})
    assert c.post("/api/instamart/cart/clear", json={"confirm": False, "idempotency_key": "clear-key-0001"}).status_code == 400 and len(ids(c)) == 2
    d = c.post("/api/instamart/cart/clear", json={"confirm": True, "idempotency_key": "clear-key-0002"}).json()
    assert d["status"] == "CONFIRMED" and d["cart"] == [] and ids(c) == {}
def test_rate_limited_search_is_reported_safely(monkeypatch):
    async def limited(*a, **k): raise swiggy.SwiggyError("Swiggy is temporarily rate-limiting requests. Please wait a minute and try again.", "MCP_RATE_LIMITED")
    monkeypatch.setattr(main.client, "search", limited)
    r = TestClient(main.app).post("/api/optimize-cart", json={"requirements": [R("rice")]}); assert r.status_code == 429 and "rate-limiting" in r.json()["detail"]

def test_reconcile_states():
    b, d = [{"product_id": "a", "packs": 1}], [{"product_id": "a", "packs": 1}, {"product_id": "b", "packs": 2}]
    assert e.reconcile(b, d, d) == "CONFIRMED" and e.reconcile(b, d, b) == "NOT_APPLIED" and e.reconcile(b, d, d[:1] + [{"product_id": "b", "packs": 1}]) == "PARTIAL"

def test_semantic_validity_beats_price():
    assert e.solve(R("chicken curry cut", 500), [P("l", 500, 10, name="Chicken Liver"), P("c", 500, 90, name="Chicken Curry Cut")])["selection"][0]["product"]["product_id"] == "c"
    assert e.solve(R("chicken curry cut", 500), [P("l", 500, 10, name="Chicken Liver")])["status"] == "no_match"
    for req, name in [("coconut milk", "Coconut Cream"), ("coriander seed", "Fresh Coriander Leaves"), ("plain yogurt", "Blueberry Yogurt"), ("butter", "Ghee")]:
        assert e.solve(R(req, 200), [P("x", 200, 5, name=name)])["selection"] == [], req
    r = e.solve(R("yogurt", 400), [P("y", 400, 5, name="Blueberry Yogurt")])
    assert r["status"] == "needs_substitute_approval" and r["candidates"][0]["match"] == "POSSIBLE_ALTERNATIVE"  # never auto-selected
    assert e.solve(R("chicken curry cut", 500), [P("c", 500, 90, name="Chicken Curry Cut")])["candidates"][0]["match"] == "EXACT_MATCH"
def test_pack_reasoning_and_unknown_quantity():
    r = e.solve(R("rice", 300), [P("a", 500, 90)]); assert (r["selection"][0]["packs"], r["excess"]) == (1, 200)
    r = e.solve(R("rice", 1200), [P("a", 500, 90)]); assert (r["selection"][0]["packs"], r["purchased"], r["excess"]) == (3, 1500, 300)
    r = e.solve(R("rice", None, None), [P("a", 500, 90)]); assert r["excess"] is None and r["purchased"] is None  # no fabricated leftover

# ---- Swiggy client: the real cause of the intermittent 502 ----
def test_parallel_searches_open_one_mcp_session():
    c, calls = ts.mk()
    async def go(): return await asyncio.gather(*[c.search(f"q{i}", "A1", ts.SID) for i in range(6)])
    asyncio.run(go()); assert sum(1 for x in calls if x[2].get("method") == "initialize") == 1
def test_reads_are_retried_on_429_but_mutations_never(monkeypatch):
    monkeypatch.setattr(swiggy, "BACKOFF", (0, 0)); n = {"search": 0, "update": 0}; ok = ts.fake([])
    def h(req):
        body = json.loads(req.content); m = body.get("method")
        if m == "initialize": return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}})
        if m == "notifications/initialized": return httpx.Response(202)
        nm = body["params"]["name"]
        if nm == "search_products": n["search"] += 1; return httpx.Response(429) if n["search"] < 3 else ok(req)
        if nm == "update_cart": n["update"] += 1; return httpx.Response(502)
        return ok(req)
    swiggy.TOKENS["retry-sess-001"] = {"token": "t", "exp": time.time() + 99}; c = swiggy.SwiggyInstamartMCPClient(transport=httpx.MockTransport(h)); sid = "retry-sess-001"
    assert len(asyncio.run(c.search("butter", "A1", sid))) == 3 and n["search"] == 3
    with pytest.raises(swiggy.SwiggyError) as x: asyncio.run(c.update_cart(sid, [{"product_id": "M1", "sku_id": "MK1", "packs": 1}], "A1"))
    assert n["update"] == 1 and x.value.kind == "MCP_UPSTREAM_ERROR"
    n["search"] = -99
    def always429(req):
        b = json.loads(req.content)
        return httpx.Response(429) if b.get("params", {}).get("name") == "search_products" else h(req)
    c2 = swiggy.SwiggyInstamartMCPClient(transport=httpx.MockTransport(always429))
    with pytest.raises(swiggy.SwiggyError) as y: asyncio.run(c2.search("x", "A1", sid))
    assert y.value.kind == "MCP_RATE_LIMITED"
def test_product_images_only_https_and_frontend_never_uses_innerhtml():
    d = json.loads(json.dumps(ts.SEARCH)); d["data"]["products"][0]["variations"][0]["imageUrl"] = "javascript:alert(1)"; d["data"]["products"][0]["variations"][1]["imageUrl"] = "https://cdn.example.com/a.png"
    def h(req):
        b = json.loads(req.content); m = b.get("method")
        if m == "initialize": return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}})
        if m == "notifications/initialized": return httpx.Response(202)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": json.dumps(d)}]}})
    swiggy.TOKENS["img-sess-00001"] = {"token": "t", "exp": time.time() + 99}
    ps = asyncio.run(swiggy.SwiggyInstamartMCPClient(transport=httpx.MockTransport(h)).search("b", "A1", "img-sess-00001"))
    assert ps[0]["image_url"] is None and ps[1]["image_url"] == "https://cdn.example.com/a.png"
    js = open(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "app.js"), encoding="utf-8").read()
    import re; assert not re.search(r"innerHTML|insertAdjacentHTML|dangerouslySetInnerHTML|document\.write", js)

def test_rate_limit_still_enforced_in_the_app(monkeypatch):
    monkeypatch.setattr(main, "LIMIT", 3); main.HITS.clear()
    c = TestClient(main.app); codes = [c.get("/api/health").status_code for _ in range(5)]
    main.HITS.clear(); assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]
def test_empty_live_cart_after_http_ok_is_not_success_and_has_diagnostic(monkeypatch):
    async def silent(sid, items, address_id=None): return None  # HTTP/MCP call "succeeds" but the cart stays empty
    monkeypatch.setattr(main.client, "update_cart", silent); c = TestClient(main.app, headers={"X-Session": "ops-empty-001"})
    d = post(c, ITEM, "op-empty-key01").json()
    assert d["status"] == "NOT_APPLIED" and d["verified"] is False and "NOT confirmed" in d["message"]
    assert d["diagnostic"]["wanted_items"] >= 1 and [m["product_id"] for m in d["diagnostic"]["missing"]] == ["may-a1"] and d["diagnostic"]["missing"][0]["found"] == 0
def test_successful_readback_is_verified_without_diagnostic():
    c = TestClient(main.app, headers={"X-Session": "ops-good-0001"}); d = post(c, ITEM, "op-good-key001").json()
    assert d["status"] == "CONFIRMED" and d["verified"] is True and d.get("diagnostic") is None
