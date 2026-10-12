import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import asyncio, engine as e, main
from fastapi.testclient import TestClient
from test_cart_ops import post, ids, ITEM


def P(i, name, q, u, price=50):
    return dict(product_id=i, name=name, brand="", variant="", pack_quantity=q, pack_unit=u, price=price, availability=True, image_url=None)


def S(line, prods):
    return e.solve(e.make_requirements([e.parse_line(line)], {})[0], prods)


def sel(r): return r["selection"][0]["product"]["name"] if r["selection"] else None


# ---- matching
def test_mint_leaves_never_match_mint_candy():
    for n in ("Impact Mints Sugar Free Mints Fresh Mints", "Polo Mints", "Mint Candy", "Fresh Mint Chewing Gum"):
        assert S("5 mint leaves", [P("a", n, 14, "g")])["status"] != "ok", n
    assert sel(S("5 mint leaves", [P("a", "Fresh Mint Leaves (Pudina)", 100, "g")])) == "Fresh Mint Leaves (Pudina)"


def test_unverified_coriander_needs_review_not_selected():
    r = S("5 coriander leaves", [P("a", "Alburyani Coriander Bright & Nutty (Dhaniya)", 100, "g")])
    assert r["status"] == "needs_substitute_approval" and not r["selection"] and r["candidates"][0]["match"] == "POSSIBLE_ALTERNATIVE"
    assert S("5 coriander leaves", [P("a", "Coriander Powder", 100, "g"), P("b", "Coriander Seeds", 100, "g")])["status"] != "ok"
    assert S("5 coriander leaves", [P("a", "Fresh Coriander Leaves", 100, "g")])["selected_match"] == "EXACT_MATCH"


def test_ginger_paste_is_not_ginger_garlic_paste():
    gg = P("a", "Everest Ginger Garlic Paste", 100, "g")
    r = S("1 tsp ginger paste", [gg]); assert r["status"] == "needs_substitute_approval" and not r["selection"]
    assert sel(S("1 tsp ginger paste", [gg, P("b", "Ginger Paste", 100, "g", 90)])) == "Ginger Paste"
    assert S("1 tsp ginger", [gg])["status"] == "no_match"


def test_other_forbidden_matches():
    assert S("100 g maida", [P("a", "Jowar Flour", 500, "g")])["status"] != "ok"
    assert S("1 green chilli", [P("a", "Red Chilli Sauce", 200, "g")])["status"] != "ok"
    assert S("200 g basmati rice", [P("a", "Sona Masoori Rice", 1000, "g")])["status"] != "ok"
    assert S("100 ml yogurt", [P("a", "Strawberry Flavoured Yogurt", 100, "g")])["status"] != "ok"


# ---- quantity math
def test_leftover_in_pack_unit_rounded_and_estimated():
    r = S("3 tbsp cooking oil", [P("a", "Saffola Cooking Oil", 850, "g")])
    assert r["purchased_unit"] == "g" and r["estimated"] and r["quantity_state"] == "estimated" and r["excess"] == 810.0
    r = S("1 tbsp ghee", [P("a", "Heritage Cow Ghee", 45, "ml")]); assert r["purchased_unit"] == "ml" and r["excess"] == 30.0
    r = S("100 ml yogurt", [P("a", "Sid's Farm Curd Pouch", 180, "g")]); assert r["purchased_unit"] == "g" and r["excess"] == 77.0
    assert all("878" not in x and "27.3" not in x for x in r["reasons"])


def test_same_unit_is_verified_and_exact():
    r = S("300 g chicken", [P("a", "Chicken Curry Cut", 500, "g")])
    assert r["quantity_state"] == "verified" and not r["estimated"] and r["excess"] == 200 and r["covers"]


def test_unverified_quantity_state():
    r = S("5 coriander leaves", [P("a", "Fresh Coriander Leaves", 100, "g")]); assert r["quantity_state"] == "unverified"


def test_coverage_indicators_are_distinct():
    items = [S("300 g chicken", [P("a", "Chicken Curry Cut", 500, "g")]), S("5 mint leaves", [P("a", "Polo Mints", 14, "g")]),
             S("1 tsp ginger paste", [P("g", "Ginger Garlic Paste", 100, "g")]), S("100 ml yogurt", [P("y", "Curd Pouch", 180, "g")])]
    c = e.coverage(items, [{"name": "salt", "status": "full"}], [])["counts"]
    assert (c["to_buy"], c["selected"], c["exact"], c["alternative"], c["needs_review"], c["unavailable"], c["pantry"]) == (4, 2, 1, 1, 1, 1, 1)


# ---- cart flow (backend half; the dialog itself is covered by the browser test)
def test_added_message_and_no_change_message():
    c = TestClient(main.app, headers={"X-Session": "mst-add-0001"}); b0 = ids(c)
    d = post(c, ITEM, "mst-key-00001").json()
    assert d["status"] == "CONFIRMED" and d["operation"] == "add" and not d["no_change"] and "verified" in d["message"] and ids(c) == {**b0, "may-a1": 1}
    d2 = post(c, ITEM, "mst-key-00002").json()
    assert d2["no_change"] is True and "No update was necessary" in d2["message"] and ids(c) == {**b0, "may-a1": 1}


def test_unrelated_items_preserved_and_no_duplicates():
    c = TestClient(main.app, headers={"X-Session": "mst-keep-0001"}); b0 = ids(c)
    post(c, [{"product_id": "hon-a1", "packs": 2}], "mst-keep-key01"); post(c, ITEM, "mst-keep-key02"); post(c, ITEM, "mst-keep-key03")
    assert ids(c) == {**b0, "hon-a1": 2, "may-a1": 1}


def test_clear_has_own_message_and_empties_cart():
    c = TestClient(main.app, headers={"X-Session": "mst-clr-00001"}); post(c, ITEM, "mst-clr-key001")
    d = c.post("/api/instamart/cart/clear", json={"confirm": True, "idempotency_key": "mst-clr-key002"}).json()
    assert d["operation"] == "clear" and d["status"] == "CONFIRMED" and "cleared" in d["message"] and "verified" in d["message"] and ids(c) == {}
    assert c.post("/api/instamart/cart/clear", json={"confirm": False, "idempotency_key": "mst-clr-key003"}).status_code == 400


def test_no_mutation_without_confirm():
    c = TestClient(main.app, headers={"X-Session": "mst-noc-00001"}); h = c.get("/api/instamart/cart").json()["hash"]; b0 = ids(c)
    r = c.post("/api/instamart/cart", json={"items": ITEM, "confirm": False, "expected_cart_hash": h, "idempotency_key": "mst-noc-key001"})
    assert r.status_code == 400 and ids(c) == b0


def test_parallel_mutation_rejected_while_in_progress():
    c = TestClient(main.app, headers={"X-Session": "mst-par-00001"}); h = c.get("/api/instamart/cart").json()["hash"]; b0 = ids(c)
    main.INFLIGHT.add("mst-par-00001")
    try: r = c.post("/api/instamart/cart", json={"items": ITEM, "confirm": True, "expected_cart_hash": h, "idempotency_key": "mst-par-key001"})
    finally: main.INFLIGHT.discard("mst-par-00001")
    assert r.status_code == 409 and r.json()["code"] == "IN_PROGRESS" and ids(c) == b0
    assert post(c, ITEM, "mst-par-key002").json()["status"] == "CONFIRMED"  # lock released afterwards


def test_order_placement_stays_disabled():
    c = TestClient(main.app); assert c.get("/api/health").json()["order_mode"] is False
    assert all("order" not in r.path.lower() or "address" in r.path.lower() for r in main.app.routes if hasattr(r, "path") and r.path.startswith("/api/instamart/") and "place" in r.path.lower()) 
