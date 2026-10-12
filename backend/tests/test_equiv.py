import sys, os, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import engine as e, instamart, main
from fastapi.testclient import TestClient
C = instamart.LocalInstamartMCPClient()
def run(line, approved=False):
    i = e.parse_line(line); rq = e.make_requirements([i], {i["name"]: "buy"})[0]
    return e.solve(rq, asyncio.run(C.search(rq["normalized_name"])), approved)
def names(r): return [c["product"]["name"] for c in r["candidates"]]

def test_quarts_unit_and_generic_oil_shows_all_cooking_oils():
    assert e.parse_line("3 1/2 quarts high temperature cooking oil")["quantity"] == 3311 and e.parse_line("3 1/2 quarts high temperature cooking oil")["unit"] == "ml"
    r = run("3 quarts high temperature cooking oil")
    assert r["status"] == "ok" and "olive" not in r["selection"][0]["product"]["name"].lower()
    assert {"Sunflower Oil", "Groundnut Oil", "Mustard Oil"} <= set(names(r)) and any("Olive" in n for n in names(r))
def test_all_purpose_flour_is_maida_without_approval():
    r = run("2 cups all-purpose flour"); assert r["status"] == "ok" and not r["unverified"]
    assert any("Maida" in n for n in names(r)) and "Also sold as" in r["candidates"][0]["reasons"][0]
def test_chicken_thighs_show_close_chicken_not_liver():
    r = run("2 lb bone-in skin-on chicken thighs")
    assert r["selection"][0]["product"]["name"] == "Chicken Thigh Bone-in"
    n = names(r); assert "Chicken Drumsticks" in n and "Chicken Liver" not in n
    boneless = next(c for c in r["candidates"] if c["product"]["name"] == "Chicken Thigh Boneless"); assert boneless["substitute"]
def test_hot_sauce_and_vinegar_list_all_kinds_and_out_of_stock():
    r = run("2 tbsp hot sauce"); assert {"Hot Sauce", "Peri Peri Hot Sauce"} <= set(names(r))
    assert [u["product"]["name"] for u in r["unavailable"]] == ["Sriracha Chilli Sauce"] and r["selection"][0]["product"]["availability"]
    v = run("1 cup white distilled vinegar"); assert {"White Vinegar", "Apple Cider Vinegar", "Balsamic Vinegar"} <= set(names(v))
def test_lime_juice_suggests_lemon_but_needs_choice():
    r = run("4 tbsp lime juice"); assert r["status"] == "needs_substitute_approval" and not r["selection"]
    assert {"Lemon", "Lime"} <= set(names(r)) and all(c["substitute"] for c in r["candidates"])
    assert run("1 lemon juice", True)["status"] == "ok"
def test_onion_does_not_pick_spring_onion_or_garlic_powder():
    assert run("2 onion")["selection"][0]["product"]["name"] == "Onion" and run("5 garlic cloves")["selection"][0]["product"]["name"] == "Garlic"
    assert run("2 green onions")["selection"][0]["product"]["name"] == "Spring Onion"
def test_buttermilk_and_the_missing_list_items_now_found():
    for line in ["1 1/2 cups buttermilk", "1 tsp mustard seeds", "1 tsp chana dal", "1 tsp whole black gram", "8 cashew nuts", "10 peanuts", "1 tsp turmeric powder",
                 "1 tbsp honey", "2 tbsp dark soy sauce", "2 tbsp sweet soy sauce", "1 tsp baking soda", "1 tsp cayenne powder", "1/2 tsp onion powder", "1 cup kimchi",
                 "2 cups green cabbage", "1/2 cup potato starch", "1 tsp white pepper", "7 jalapenos", "1 tbsp gochujang", "2 3/4 tsp MSG", "2 tbsp kosher salt"]:
        assert run(line, True)["status"] == "ok", line
def test_cart_traces_source_and_ignores_client_price():
    c = TestClient(main.app, headers={"X-Session": "trace-1"}); h = c.get("/api/instamart/cart").json()["hash"]
    r = c.post("/api/instamart/cart", json={"items": [{"product_id": "may-a1", "packs": 1, "source": "Mayonnaise", "price": 1}], "confirm": True, "expected_cart_hash": h, "idempotency_key": "trace-key-1"}).json()
    it = next(i for i in r["after"] if i["product_id"] == "may-a1"); assert it["source_ingredient"] == "Mayonnaise" and it["price"] == 95.0
    assert c.post("/api/instamart/cart", json={"items": [{"product_id": "fake-123", "packs": 1}], "confirm": True, "expected_cart_hash": "x", "idempotency_key": "trace-key-2"}).status_code in (400, 409)
