"""Generic matching pipeline: no ingredient-specific code paths are exercised here, only unfamiliar ingredients and live-shaped products."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import asyncio, engine as e, main, swiggy
from fastapi.testclient import TestClient


def P(i, name, q, u, price=30, brand="", av=True):
    return dict(product_id=i, name=name, brand=brand, variant=None, category=None, pack_quantity=q, pack_unit=u, price=price, availability=av, image_url=None, pack_label=f"{q:g} {u}")


def S(line, prods, **k):
    return e.solve(e.make_requirements([e.parse_line(line)], {})[0], prods, **k)


def sel(r): return [l["product"]["name"] for l in r["selection"]]


def test_root_cause_bunch_packs_are_parsed_not_dropped():
    assert swiggy.parse_pack("1 Bunch") == (1, "bunch") and swiggy.parse_pack("2 Bunches") == (2, "bunch") and swiggy.parse_pack("1 Combo") == (1, "combo")
    assert swiggy.parse_pack("500 g") == (500, "g") and swiggy.parse_pack("Assorted") is None


def test_live_shaped_mint_results_recipe_vs_manual_search():
    live = [P("1", "nectr Mint Leaves", 1, "bunch", 12, "nectr"), P("2", "Doublemint Peppermint Flavour Chewy Mint", 3.2, "g", 10, "Doublemint"), P("3", "Mint Leaves With Stem", 1, "bunch", 11, "Fruits & Vegetables Category"),
            P("4", "Tic Tac Mint", 13, "g", 20, "Tic Tac"), P("5", "Mint Leaves & Curry Leaves", 1, "combo", 20, "Fruits & Vegetables Category"), P("6", "Doublemint Peppermint Flavour Classic Chewing Gum", 13, "g", 10),
            P("7", "Impact Mints Strong Mint Sugar Free", 14, "g", 150), P("8", "Mentos Mint Flavour Chewy Candy Stick", 36.4, "g", 20), P("9", "Impact Mints Sugar Free Mints Fresh Mints", 14, "g", 150)]
    for line in ("10 mint leaves", "1 tbsp fresh mint", "2 mint leaves"):
        r = S(line, live)
        assert r["status"] == "ok" and sel(r)[0] in ("nectr Mint Leaves", "Mint Leaves With Stem"), (line, sel(r))
        names = {c["product"]["name"] for c in r["candidates"]}
        assert not any(w in n for n in names for w in ("Chew", "Gum", "Sugar Free", "Candy")), names
        assert r["selection"][0]["product"]["product_id"] in {p["product_id"] for p in live}  # recipe matching only ever picks products the live search returned
    assert S("10 mint leaves", live)["quantity_state"] == "unverified"  # pieces vs bunch: not comparable, say so


def test_bunch_quantity_compares_with_bunch_packs():
    r = S("2 bunch coriander leaves", [P("a", "Coriander Leaves", 1, "bunch", 10), P("b", "Coriander Powder", 100, "g")])
    assert sel(r) == ["Coriander Leaves"] and r["selection"][0]["packs"] == 2 and r["quantity_state"] == "verified"


def test_unfamiliar_ingredients_across_recipes():
    cases = [("200 g paneer", [P("a", "Amul Fresh Paneer", 200, "g", 90), P("b", "Paneer Masala Mix", 50, "g")], "Amul Fresh Paneer"),
             ("2 tbsp tamarind paste", [P("a", "Tamarind Paste", 100, "g", 40), P("b", "Tamarind Candy", 50, "g", 20)], "Tamarind Paste"),
             ("1 cup quinoa", [P("a", "Quinoa", 500, "g", 200), P("b", "Quinoa Chips", 100, "g")], "Quinoa"),
             ("300 g salmon fillet", [P("a", "Salmon Fillet", 300, "g", 600), P("b", "Salmon Flavoured Cat Food", 300, "g", 100)], "Salmon Fillet"),
             ("1 tsp saffron", [P("a", "Saffron Kesar", 1, "g", 300)], "Saffron Kesar")]
    for line, prods, want in cases:
        r = S(line, prods); assert sel(r) == [want], (line, sel(r), r["status"])


def test_powder_vs_whole_and_fresh_vs_processed():
    assert S("1 tsp cumin seeds", [P("a", "Cumin Powder", 100, "g"), P("b", "Cumin Seeds (Jeera)", 100, "g")]) ["selection"][0]["product"]["name"] == "Cumin Seeds (Jeera)"
    assert not S("1 tsp cumin seeds", [P("a", "Cumin Powder", 100, "g")])["selection"]
    assert not S("5 coriander leaves", [P("a", "Coriander Powder", 100, "g")])["selection"]
    assert not S("200 g chicken", [P("a", "Chicken Flavour Chips", 50, "g"), P("b", "Chicken Seekh Kebab", 200, "g")])["selection"]


def test_unavailable_only_after_real_search_and_errors_are_not_unavailable():
    out = S("10 mint leaves", [P("a", "Mint Leaves", 1, "bunch", 12, av=False)])
    assert out["status"] == "no_match" and out["unavailable"]  # out of stock is reported as such
    f = e.failed_result(e.make_requirements([e.parse_line("1 tsp saffron")], {})[0]); assert f["status"] == "search_failed" and f["outcome"] == "search_failed"
    assert e.coverage([f], [], [])["rows"][0]["state"] == "search_failed"
    assert e.coverage([S("1 tsp saffron", [])], [], [])["rows"][0]["state"] == "missing"


def test_search_terms_are_bounded_and_deduplicated():
    for line in ("2 tbsp fresh cilantro", "10 mint leaves", "1 cup quinoa", "200 g paneer"):
        t = e.search_terms(e.make_requirements([e.parse_line(line)], {})[0]); assert 1 <= len(t) <= 6 and len(t) == len(set(t))


def test_pack_selection_and_leftover_math():
    r = S("300 g paneer", [P("a", "Paneer", 200, "g", 90), P("b", "Paneer", 500, "g", 200)])
    assert r["covers"] and r["purchased"] >= 300
    r = S("200 g rice", [P("a", "Rice", 1000, "g", 69)]); assert r["excess"] == 800 and r["quantity_state"] == "verified"


def test_no_duplicate_cart_lines_from_repeated_requirements():
    rq = e.make_requirements([e.parse_line(x) for x in ("200 g rice", "100 g rice", "1 tbsp fresh mint", "5 mint leaves")], {})
    assert [r["normalized_name"] for r in rq].count("rice") == 1 and len(rq) == 3 - (0 if len(rq) == 3 else 1)
    assert sum(r["required_quantity"] or 0 for r in rq if r["normalized_name"] == "rice") == 300


def test_manual_search_endpoint_uses_same_live_catalog_as_recipe_matching():
    c = TestClient(main.app, headers={"X-Session": "gen-0000001"})
    manual = c.get("/api/instamart/products", params={"q": "milk"}).json()["products"]
    ing = c.post("/api/optimize-cart", json={"requirements": [{"requirement_id": "r1", "ingredient_name": "milk", "normalized_name": "milk", "required_quantity": 200, "unit": "ml", "optional": False}], "overrides": {}, "pack_counts": {}, "approved_substitutes": [], "have": [], "skipped": []}).json()
    ids = {p["product_id"] for p in manual}
    assert ing["items"][0]["selection"] and ing["items"][0]["selection"][0]["product"]["product_id"] in ids
