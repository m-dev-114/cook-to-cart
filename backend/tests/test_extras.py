import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import engine as e, main
from fastapi.testclient import TestClient
from test_cart_ops import ids


def P(i, name, q, u, price=50):
    return dict(product_id=i, name=name, brand="", variant="", pack_quantity=q, pack_unit=u, price=price, availability=True, image_url=None)


def S(line, prods):
    return e.solve(e.make_requirements([e.parse_line(line)], {})[0], prods)


def sel(r): return r["selection"][0]["product"]["name"] if r["selection"] else None


def test_fresh_mint_never_matches_gum_or_breath_mints():
    junk = [P("a", "Mentos Pure Fresh Sugarfree Fresh Mint Chewing Gum PB", 58, "g"), P("b", "Impact Mints Sugar Free Mints Fresh Mints", 14, "g"), P("c", "Tic Tac Mint", 13, "g"),
            P("d", "Happydent Wave Sugarfree Mint Flavour Chewing Gum", 30, "g"), P("e", "Colgate Mint Toothpaste", 100, "g")]
    r = S("1 tbsp fresh mint", junk); assert not r["selection"] and r["status"] in ("no_match", "needs_substitute_approval")  # never auto-selected
    assert all(c["match"] == "POSSIBLE_ALTERNATIVE" and "Tic Tac" in c["product"]["name"] for c in r["candidates"])  # gum, sugar-free mints, toothpaste are rejected outright
    assert sel(S("1 tbsp fresh mint", junk + [P("f", "Pudina (Mint Leaves) Bunch", 100, "g")])) == "Pudina (Mint Leaves) Bunch"


def test_fresh_cilantro_finds_coriander_leaves_not_seeds_or_powder():
    r = S("2 tbsp fresh cilantro", [P("a", "Coriander Leaves", 100, "g"), P("b", "Coriander Powder", 100, "g"), P("c", "Coriander Seeds", 100, "g")])
    assert sel(r) == "Coriander Leaves" and len(r["candidates"]) == 1
    assert "coriander leaf" in e.search_terms(e.make_requirements([e.parse_line("2 tbsp fresh cilantro")], {})[0])


def test_basmati_vs_broken_basmati():
    r = S("200 g basmati rice", [P("a", "921 Rozana Broken Basmati Rice", 1000, "g", 69), P("b", "Daawat Basmati Rice", 1000, "g", 140)])
    assert sel(r) == "Daawat Basmati Rice"
    only = S("200 g basmati rice", [P("a", "921 Rozana Broken Basmati Rice", 1000, "g", 69)])
    assert only["status"] == "needs_substitute_approval" and only["candidates"][0]["match"] == "POSSIBLE_ALTERNATIVE"


def test_plain_yogurt_not_protein_or_flavoured():
    r = S("100 ml yogurt", [P("a", "Epigamia Turbo 17 g Protein Yogurt, Natural", 140, "g", 125), P("b", "Strawberry Flavoured Yogurt", 100, "g"), P("c", "Mother Dairy Curd", 400, "g", 40)])
    assert sel(r) == "Mother Dairy Curd" and len(r["candidates"]) == 1


def test_smallest_suitable_pack_preferred():
    r = S("200 g rice", [P("a", "Rice", 1000, "g", 69), P("b", "Rice", 500, "g", 40), P("c", "Rice", 250, "g", 38)])
    assert r["selection"][0]["product"]["product_id"] == "c" and r["selection"][0]["packs"] == 1


def test_duplicate_ingredients_merge_before_matching():
    ings = [e.parse_line(x) for x in ("200 g rice", "100 g rice", "1 tbsp fresh cilantro", "1 tbsp coriander leaves")]
    rq = e.make_requirements(ings, {})
    assert len(rq) == 2 and rq[0]["required_quantity"] == 300
    assert len(e.consolidate(ings)) == 2


def test_additional_item_search_add_and_final_update_include_it():
    c = TestClient(main.app, headers={"X-Session": "xtra-0000001"}); b0 = ids(c)
    prods = c.get("/api/instamart/products", params={"q": "bread"}).json()["products"]
    assert prods and all(p["product_id"] and p["price"] is not None for p in prods) and len({p["product_id"] for p in prods}) == len(prods)
    assert c.get("/api/instamart/products", params={"q": "zzzqqq"}).json()["products"] == []
    pid = prods[0]["product_id"]; h = c.get("/api/instamart/cart").json()["hash"]
    items = [{"product_id": pid, "packs": 2, "source": "Additional item"}, {"product_id": pid, "packs": 1, "source": "Additional item"}]  # same product twice: one line, summed
    d = c.post("/api/instamart/cart", json={"items": items, "confirm": True, "expected_cart_hash": h, "idempotency_key": "xtra-key-0001"}).json()
    assert d["status"] == "CONFIRMED" and ids(c)[pid] >= 3 and all(v == b0[k] for k, v in b0.items() if k != pid)


def test_unknown_additional_product_rejected_and_never_added():
    c = TestClient(main.app, headers={"X-Session": "xtra-0000002"}); h = c.get("/api/instamart/cart").json()["hash"]; b0 = ids(c)
    r = c.post("/api/instamart/cart", json={"items": [{"product_id": "made-up-123", "packs": 1}], "confirm": True, "expected_cart_hash": h, "idempotency_key": "xtra-key-0002"})
    assert r.status_code == 400 and ids(c) == b0
    assert c.get("/api/instamart/products", params={"q": "x" * 500}).status_code == 422
