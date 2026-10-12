import sys, os, re, json, time, asyncio, subprocess; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import httpx, pytest, engine as e, instamart, main, swiggy, test_swiggy as ts
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(__file__)); FE = os.path.join(ROOT, "..", "frontend")
def P(i, q, price, u="g", name="Garlic", av=True):
    return dict(product_id=i, name=name, brand="B", category=None, variant=None, pack_quantity=q, pack_unit=u, price=price, availability=av, image_url=None)
def R(n, q=100, u="g"): return dict(requirement_id="r1", ingredient_name=n, normalized_name=n, required_quantity=q, unit=u, category=None, optional=False, notes=None)
RQ = [e.make_requirements([e.parse_line("500 g rice")], {"rice": "buy"})[0]]

def test_address_must_be_chosen_and_must_belong_to_the_account(monkeypatch):
    monkeypatch.setattr(main, "MODE", "swiggy"); main.ADDR.clear(); c = TestClient(main.app, headers={"X-Session": "addr-sess-0001"})
    r = c.post("/api/optimize-cart", json={"requirements": RQ}); assert r.status_code == 409 and "delivery address" in r.json()["detail"]  # no search before an address
    assert c.post("/api/instamart/address", json={"address_id": "someone-elses-address"}).status_code == 403
    assert c.post("/api/instamart/address", json={"address_id": "demo-1"}).status_code == 200
    assert c.post("/api/optimize-cart", json={"requirements": RQ}).status_code == 200
    assert TestClient(main.app, headers={"X-Session": "addr-sess-0002"}).post("/api/optimize-cart", json={"requirements": RQ}).status_code == 409  # another session isn't covered
    r = c.post("/api/instamart/cart", json={"items": [{"product_id": "may-a1", "packs": 1}], "confirm": True, "expected_cart_hash": "x", "idempotency_key": "addr-key-00001"}); assert r.status_code in (409, 200)
def test_price_change_stops_the_update_for_review(monkeypatch):
    c = TestClient(main.app, headers={"X-Session": "price-sess-001"}); h = c.get("/api/instamart/cart").json()["hash"]
    async def repriced(pid, sid=None, address_id=None): return {**instamart.CATALOG[pid], "price": instamart.CATALOG[pid]["price"] + 20}
    monkeypatch.setattr(main.client, "revalidate", repriced)
    r = c.post("/api/instamart/cart", json={"items": [{"product_id": "may-a1", "packs": 1}], "confirm": True, "expected_cart_hash": h, "idempotency_key": "price-key-0001"})
    d = r.json(); assert r.status_code == 409 and d["status"] == "FAILED_BEFORE_MUTATION" and d["price_changes"][0]["now"] == d["price_changes"][0]["was"] + 20 and "review" in d["detail"]
    assert "may-a1" not in [i["product_id"] for i in c.get("/api/instamart/cart").json()["items"]]
def test_forms_of_the_same_vegetable_are_ineligible_not_alternatives():
    for req, name in [("ginger", "Ginger Paste"), ("garlic", "Garlic Paste"), ("garlic", "Garlic Powder"), ("onion", "Spring Onion"), ("coriander leaf", "Coriander Seeds")]:
        assert e.solve(R(req), [P("x", 100, 5, name=name)])["status"] == "no_match", (req, name)
    assert e.solve(R("garlic"), [P("a", 100, 30, name="Garlic Paste"), P("b", 100, 40, name="Garlic")])["selection"][0]["product"]["product_id"] == "b"
    assert e.solve(R("butter"), [P("g", 100, 5, name="Ghee")])["status"] == "no_match" and e.solve(R("chicken", 500), [P("l", 500, 5, name="Chicken Liver")])["status"] == "no_match"
    assert e.solve(R("chicken", 500), [P("b", 500, 50, name="Chicken Breast")])["selection"][0]["product"]["name"] == "Chicken Breast"  # a legitimate variant, offered as a choice
def test_ingredient_record_has_the_spec_fields():
    p = e.parse_line("2 medium onions, finely chopped")
    assert (p["canonical_name"], p["quantity"], p["unit"], p["size"], p["preparation"], p["quantity_confidence"], p["raw_text"]) == ("onion", 2, "piece", "medium", "finely chopped", "explicit", "2 medium onions, finely chopped")
    assert e.parse_line("salt to taste")["quantity_confidence"] == "unknown" and e.parse_line("1/2 cup carrot")["quantity_confidence"] == "estimated"
def test_live_is_the_default_and_demo_must_be_explicit():
    env = {k: v for k, v in os.environ.items() if k != "INSTAMART_MODE"}
    out = subprocess.run([sys.executable, "-c", "import main; print(main.MODE)"], cwd=ROOT, env=env, capture_output=True, text=True).stdout.split()[-1]; assert out == "swiggy"
    assert "demo catalog" in instamart.LocalInstamartMCPClient.label.lower() or "mock" in instamart.LocalInstamartMCPClient.label.lower()
def test_live_failure_shows_an_error_never_fake_products(monkeypatch):
    monkeypatch.setattr(swiggy, "BACKOFF", (0, 0)); swiggy.TOKENS["fail-sess-0001"] = {"token": "t", "exp": time.time() + 99}
    def h(req):
        b = json.loads(req.content)
        if b.get("method") == "initialize": return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}})
        if b.get("method") == "notifications/initialized": return httpx.Response(202)
        return httpx.Response(502)
    c = swiggy.SwiggyInstamartMCPClient(transport=httpx.MockTransport(h))
    with pytest.raises(swiggy.SwiggyError): asyncio.run(c.search("rice", "A1", "fail-sess-0001"))
    assert "CATALOG" not in open(os.path.join(ROOT, "swiggy.py")).read() and "import instamart" not in open(os.path.join(ROOT, "swiggy.py")).read()
def test_live_cart_total_is_read_from_get_cart():
    c, _ = ts.mk(); asyncio.run(c.get_cart(ts.SID)); assert c.totals[ts.SID] == 58.0
def test_complete_cart_is_sent_so_unrelated_items_survive():
    c, calls = ts.mk(); asyncio.run(c.search("butter", "A1", ts.SID)); before = asyncio.run(c.get_cart(ts.SID))
    desired, ch = e.plan_cart(before, [{"product_id": "S1", "name": "Butter", "packs": 1, "price": 56}]); asyncio.run(c.update_cart(ts.SID, desired))
    sent = [x[2]["params"]["arguments"] for x in calls if x[2].get("params", {}).get("name") == "update_cart"][0]["items"]
    assert {i["spinId"] for i in sent} == {"M1", "S1"} and next(i for i in sent if i["spinId"] == "M1")["quantity"] == 2  # existing Milk x2 preserved
def test_frontend_files_are_consistent_and_safe():
    js = open(os.path.join(FE, "app.js"), encoding="utf-8").read(); html = open(os.path.join(FE, "index.html"), encoding="utf-8").read()
    v = re.search(r'name="app-version" content="(\d+)"', html).group(1)
    assert f'm.content!=="{v}"' in js and f"app.js?v={v}" in html  # the version-mismatch banner exists and matches
    assert js.count("LIVE SWIGGY INSTAMART") == 1 and js.index("LIVE SWIGGY INSTAMART") > js.index("async function loadAddresses")
    assert not re.search(r"localStorage|innerHTML|insertAdjacentHTML|dangerouslySetInnerHTML|VITE_|GEMINI|GROQ|gsk_|access_token", js)
    assert set(re.findall(r'\$\("([a-z0-9]+)"\)', js)) <= set(re.findall(r'id="([a-z0-9]+)"', html))
