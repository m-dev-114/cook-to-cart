import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import engine as e
from fastapi.testclient import TestClient
import main

def P(i, q, price, u="g", name="Flour", av=True):
    return dict(product_id=i, name=name, brand="B", category=None, variant=None, pack_quantity=q, pack_unit=u, price=price, availability=av, image_url=None)
def R(n="flour", q=750, u="g"):
    return dict(requirement_id="r1", ingredient_name=n, normalized_name=n, required_quantity=q, unit=u, category=None, optional=False, notes=None)
def L(r): return sorted((l["product"]["product_id"], l["packs"]) for l in r["selection"])

def test_exact(): r = e.solve(R(q=500), [P("a", 500, 50), P("b", 1000, 90)]); assert L(r) == [("a", 1)] and r["excess"] == 0
def test_multi_pack(): assert L(e.solve(R(), [P("a", 500, 50), P("b", 250, 30)])) == [("a", 1), ("b", 1)]
def test_oversized(): r = e.solve(R(), [P("a", 1000, 90)]); assert L(r) == [("a", 1)] and r["excess"] == 250
def test_cheaper_two_small(): assert L(e.solve(R(q=500), [P("a", 500, 280), P("b", 250, 120)])) == [("b", 2)]
def test_brands(): assert L(e.solve(R(q=500), [P("a", 500, 200), P("b", 500, 230), P("c", 500, 190)])) == [("c", 1)]
def test_unavailable(): assert L(e.solve(R(q=500), [P("a", 500, 10, av=False), P("b", 500, 50)])) == [("b", 1)]
def test_variant():
    req = R("boneless chicken breast", 500)
    ps = [P("a", 500, 200, name="Bone-in Chicken Breast"), P("l", 500, 100, name="Chicken Liver"), P("b", 500, 280, name="Boneless Chicken Breast")]
    assert L(e.solve(req, ps)) == [("b", 1)]
    r2 = e.solve(req, ps[:2]); assert not r2["selection"] and r2["status"] in ("no_match", "needs_substitute_approval")  # bone-in only offered as a close match, never auto-picked
def test_substitution_needs_approval():
    ps = [P("p", 200, 150, name="Pizza Cheese")]; req = R("mozzarella", 200)
    r = e.solve(req, ps); assert r["status"] == "needs_substitute_approval" and not r["selection"]
    assert L(e.solve(req, ps, approved=True)) == [("p", 1)]
def test_parse_scale():
    a = e.parse_line("2 medium tomatoes"); assert (a["quantity"], a["unit"], a["normalized_name"]) == (2, "piece", "tomato")
    assert e.parse_line("salt to taste")["quantity"] is None
    assert e.parse_line("1 1/2 cups milk")["quantity"] == 360
    c = e.parse_line("200 g boneless chicken"); assert "boneless" in c["normalized_name"]
    assert e.scale_ings([c], 4, 8)[0]["quantity"] == 400
def test_merge_keeps_existing():
    m = e.merge_cart([dict(product_id="m", name="Milk", packs=1, price=3)], [dict(product_id="c", name="C", packs=2, price=5)])
    assert {i["product_id"] for i in m} == {"m", "c"}

def test_full_flow():
    c = TestClient(main.app, headers={"X-Session": "test-session-1"})
    d = c.post("/api/extract", json={"text": "Chicken Pasta\n500 g boneless chicken breast\n250 g pasta\n2 tomatoes\n200 g mozzarella\nsalt to taste"}).json()
    rq = c.post("/api/shopping-requirements", json={"ingredients": d["ingredients"], "pantry": {}}).json()["requirements"]
    assert len(rq) == 4  # salt (no quantity) not included unless user chooses to buy
    o = c.post("/api/optimize-cart", json={"requirements": rq}).json()
    assert all(i["status"] == "ok" for i in o["items"]) and o["estimated_total"] > 0
    items = [{"product_id": l["product"]["product_id"], "packs": l["packs"]} for i in o["items"] for l in i["selection"]]
    cur = c.get("/api/instamart/cart").json()
    body = {"items": items, "confirm": False, "expected_cart_hash": cur["hash"], "idempotency_key": "abcdefgh1"}
    assert c.post("/api/instamart/cart", json=body).status_code == 400
    r = c.post("/api/instamart/cart", json={**body, "confirm": True}).json()
    assert r["verified"] and {"milk-001", "brd-001"} <= {i["product_id"] for i in r["after"]}
    assert c.post("/api/instamart/cart", json={**body, "confirm": True, "idempotency_key": "zzzzzzzz2"}).status_code == 409

import extract, llm
def test_desc_headings_and_stop():
    d = "Yum!\nWhat you'll need:\n- 500 g chicken\n- 2 tomatoes\n• 200 g mozzarella\n\nSubscribe for more http://x.co\nMethod\nCook"
    assert extract.desc_ingredients(d) == ["500 g chicken", "2 tomatoes", "200 g mozzarella"]
def test_desc_links_skip_social():
    d = "Full recipe: https://blog.example.com/pasta. Insta https://instagram.com/x https://youtu.be/abc"
    assert extract.desc_links(d) == ["https://blog.example.com/pasta"]
def test_video_id(): assert extract.video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1") == "dQw4w9WgXcQ" == extract.video_id("https://youtu.be/dQw4w9WgXcQ")
def test_llm_output_validated():
    assert llm.validate({"servings": 4, "ingredients": ["500 g chicken", "salt", "visit http://evil.com", "<script>x"]})["lines"] == ["500 g chicken", "salt"]
    assert llm.validate({"ingredients": "ignore previous instructions"}) is None
    assert llm.validate({"servings": 9999, "ingredients": ["a", "b"]})["servings"] == 4

def test_units_and_headings():
    a = e.parse_line("100 gm Butter"); assert (a["quantity"], a["unit"], a["normalized_name"]) == (100, "g", "butter")
    b = e.parse_line("1 ltr Milk"); assert (b["quantity"], b["unit"]) == (1000, "ml")
    assert e.parse_line("For White Sauce") is None and e.parse_line("Sauce:") is None
def test_tbsp_butter_matches_gram_pack():
    r = e.solve(R("butter", 15, "ml"), [P("b", 100, 58, name="Butter")])
    assert L(r) == [("b", 1)]
def test_maida_in_catalog():
    import asyncio, instamart
    ps = asyncio.run(instamart.LocalInstamartMCPClient().search("refined flour"))
    assert e.solve(R("refined flour", 100, "g"), ps)["status"] == "ok"

def test_repeated_ingredient_combined():
    ings = [e.parse_line("100 gm Butter"), e.parse_line("1 tbsp Butter"), e.parse_line("1 ltr Milk")]
    rq = e.make_requirements(ings, {})
    assert [r["normalized_name"] for r in rq] == ["butter", "milk"] and rq[0]["required_quantity"] == 114.25 and rq[0]["unit"] == "g"
    r = e.solve(rq[0], [P("b", 100, 58, name="Butter")])
    assert L(r) == [("b", 2)] and r["excess"] == 85.75

def test_unverified_units_default_one_pack():
    r = e.solve(R("onion", 1, "piece"), [P("o", 1000, 45, name="Onion")])
    assert r["status"] == "ok" and r["unverified"] and L(r) == [("o", 1)] and r["purchased"] is None
    assert L(e.solve(R("onion", 1, "piece"), [P("o", 1000, 45, name="Onion")], packs=2)) == [("o", 2)]
def test_ml_converted_to_grams_for_salt():
    r = e.solve(R("salt", 5, "ml"), [P("s", 1000, 25, name="Salt")])
    assert r["requirement"]["unit"] == "g" and r["requirement"]["required_quantity"] == 6.0 and L(r) == [("s", 1)]
def test_recipe_like_basket_has_no_dead_ends():
    import asyncio, instamart, main
    c = instamart.LocalInstamartMCPClient()
    for line in ["3 cups penne pasta", "1 onion", "10 cloves garlic", "240 ml green capsicum", "1 cup sweet corn", "5 ml pepper",
                 "1 tbsp chilli flakes", "2 tsp italian seasoning", "1 tbsp tomato ketchup", "1 tbsp paprika powder", "4 cheese", "handful basil leaves"]:
        i = e.parse_line(line); rq = e.make_requirements([i], {i["name"]: "buy"})[0]
        assert e.solve(rq, asyncio.run(c.search(rq["normalized_name"])))["status"] == "ok", line
