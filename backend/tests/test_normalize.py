import sys, os, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest, engine as e, extract, llm, main, instamart
from fastapi.testclient import TestClient
C = TestClient(main.app)
P = e.parse_line

def test_solids_by_cup_become_grams_not_ml():
    pasta = P("2 cups penne pasta"); assert (pasta["unit"], pasta["quantity"], pasta["source_text"], pasta["normalized_is_estimate"]) == ("g", 201.6, "2 cups", True)
    for l in ["1/4 cup carrot", "1 cup green capsicum", "1/2 cup onion"]: assert P(l)["unit"] == "g", l
    assert P("500 ml milk")["unit"] == "ml" and P("1 tbsp oil")["unit"] == "ml" and not P("500 ml milk")["normalized_is_estimate"]
def test_source_quantity_preserved():
    c = P("1/2 green capsicum"); assert (c["source_text"], c["quantity"], c["unit"], c["est_piece_g"]) == ("½ piece", 0.5, "piece", 120)
    g = P("5 garlic cloves"); assert (g["source_text"], g["unit"], g["est_piece_g"]) == ("5 cloves", "piece", 4)
    assert P("4 cheese slices")["source_text"] == "4 slices"
def test_butter_tbsp_and_piece():
    b = P("3 Tbsp. butter"); assert (b["unit"], b["source_text"]) == ("g", "3 tbsp") and b["normalized_is_estimate"]
    p = P("3 pieces butter"); assert p["unit"] == "piece" and p["est_piece_g"] == 10
def test_countable_matches_gram_pack():
    for line in ["5 garlic cloves", "1/2 carrot", "2 onion"]:
        i = P(line); rq = e.make_requirements([i], {i["name"]: "buy"})[0]
        r = e.solve(rq, asyncio.run(instamart.LocalInstamartMCPClient().search(rq["normalized_name"])))
        assert r["status"] == "ok" and not r["unverified"] and r["requirement"]["unit"] == "g" and r["requirement"]["original"], line
    r = e.solve(e.make_requirements([P("5 garlic cloves")], {"garlic": "buy"})[0], [instamart.CATALOG["gar-a1"]])
    assert r["selection"][0]["product"]["pack_unit"] == "g" and r["requirement"]["original"] == "5 cloves"
def test_cheese_slices_use_slice_pack():
    i = P("4 cheese slices"); rq = e.make_requirements([i], {i["name"]: "buy"})[0]
    r = e.solve(rq, asyncio.run(instamart.LocalInstamartMCPClient().search("cheese slice")))
    assert r["selection"][0]["product"]["name"] == "Cheese Slices"
def test_duplicates_consolidated():
    r = e.consolidate([P("2.5 ml salt"), P("2.5 ml salt"), P("2.5 ml pepper"), P("1.25 ml pepper"), P("2 cloves garlic")])
    d = {i["normalized_name"]: i for i in r}
    assert d["salt"]["quantity"] == 5 and d["salt"]["source_text"] == "5 ml" and d["pepper"]["quantity"] == 3.75 and len(r) == 3
def test_scaling_keeps_natural_units():
    s = e.scale_ings([P("5 garlic cloves"), P("1/2 capsicum"), P("500 ml milk")], 3, 6)
    assert [i["source_text"] for i in s] == ["10 cloves", "1 piece", "1000 ml"] and s[2]["quantity"] == 1000
    assert C.post("/api/scale", json={"ingredients": [P("5 garlic cloves")], "from_servings": 3, "to_servings": 6}).json()["ingredients"][0]["source_text"] == "10 cloves"
def test_detect_routes():
    assert main.detect("Paneer Butter Masala for 2") == "dish" and main.detect("https://youtu.be/dQw4w9WgXcQ") == "url" and main.detect("www.x.com/r") == "url"
    assert main.detect("Pasta\n500 g penne\n2 tomatoes") == "text"
def test_dish_name_goes_to_groq(monkeypatch):
    seen = {}
    async def gen(d, s):
        seen.update(d=d, s=s); return {"title": "Paneer Butter Masala", "servings": s, "steps": ["Cook"], "partial": False, "ingredients": [
            {"name": "paneer", "quantity": "250 g", "confidence": "estimated", "seen_at": None, "conflict": None},
            {"name": "garlic", "quantity": "5 cloves", "confidence": "estimated", "seen_at": None, "conflict": None}]}
    monkeypatch.setattr(llm, "KEY", "k"); monkeypatch.setattr(llm, "generate_recipe", gen)
    d = C.post("/api/extract", json={"input": "Paneer Butter Masala for 2"}).json()
    assert seen == {"d": "Paneer Butter Masala", "s": 2} and d["servings"] == 2 and d["source"].startswith("AI-generated") and d["ingredients"][1]["source_text"] == "5 cloves" and d["ingredients"][0]["confidence"] == "estimated"
def test_dish_without_key_or_on_groq_failure(monkeypatch):
    monkeypatch.setattr(llm, "KEY", None); r = C.post("/api/extract", json={"input": "White Sauce Pasta for 3"}); assert r.status_code == 422 and "GROQ_API_KEY" in r.json()["detail"]
    async def boom(d, s): raise RuntimeError("x")
    monkeypatch.setattr(llm, "KEY", "k"); monkeypatch.setattr(llm, "generate_recipe", boom)
    assert C.post("/api/extract", json={"input": "Chicken Biryani"}).status_code == 422
def test_url_input_uses_safe_fetch_path(monkeypatch):
    got = {}
    async def fake(u, ip="?"): got["u"] = u; return {"title": "T", "servings": 2, "lines": ["2 eggs"], "source": "x"}
    monkeypatch.setattr(extract, "from_url", fake)
    assert C.post("/api/extract", json={"input": "www.example.com/recipe"}).status_code == 200 and got["u"] == "https://www.example.com/recipe"
    got.clear(); assert C.post("/api/extract", json={"input": "http://127.0.0.1/x"}).status_code in (200, 422)
def test_pasted_text_still_works():
    d = C.post("/api/extract", json={"input": "Chicken Pasta\n500 g boneless chicken breast\n250 g pasta\n2 tomatoes"}).json()
    assert d["source"] == "pasted text" and len(d["ingredients"]) == 3

def _solve(line):
    i = P(line); rq = e.make_requirements([i], {i["name"]: "buy"})[0]
    return i, e.solve(rq, asyncio.run(instamart.LocalInstamartMCPClient().search(rq["normalized_name"])))
def test_hindi_dashes_inch_unit_cleaned():
    i = P("1 inch Ginger - (अदरक)")
    assert (i["name"], i["unit"], i["source_text"], i["normalized_is_estimate"]) == ("Ginger", "g", "1 inch", True) and not i["notes"]
    assert P("2 tbsp Oil (तेल)")["name"] == "Oil" and P("1½ tsp salt")["source_text"] == "1 ½ tsp" and P("½ tsp salt")["quantity"] > 0
def test_part_of_whole_item_maps_to_whole_product():
    i, r = _solve("1 tbsp Coriander Stems - (धनिए के डंठल)")
    assert i["normalized_name"] == "fresh coriander" and "whole item" in i["notes"] and r["status"] == "ok"
    assert r["selection"][0]["product"]["name"] == "Fresh Coriander Leaves"  # not the powder
def test_ginger_and_green_chillies_found():
    for line in ["1 inch Ginger -", "2 fresh Green Chillies -"]:
        i, r = _solve(line); assert r["status"] == "ok" and r["requirement"]["unit"] == "g", line
    assert _solve("1 inch Ginger")[1]["selection"][0]["product"]["name"] == "Fresh Ginger"
def test_not_in_store_says_so():
    assert _solve("1 tsp truffle oil shavings")[1]["status"] in ("no_match", "needs_substitute_approval")
