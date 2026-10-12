import sys, os, asyncio, json, re; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest, engine as e, extract, visual, llm, main
from fastapi.testclient import TestClient

def page(desc, secs=120):
    return f'<title>Egg snack - YouTube</title>"lengthSeconds":"{secs}" "shortDescription":"{desc}","isCrawlable":true'
URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
def run(coro): return asyncio.run(coro)
def setup(monkeypatch, html, enabled, analyze=None, tr=None):
    async def fake_fetch(u): return html
    monkeypatch.setattr(extract, "fetch", fake_fetch)
    monkeypatch.setattr(extract, "_transcript", lambda v: (tr, None if tr else "NoTranscriptFound"))
    monkeypatch.setattr(visual, "ENABLED", enabled)
    calls = []
    async def fake_an(*a, **k): calls.append(1); return analyze(*a) if analyze else (_ for _ in ()).throw(visual.VisualError("boom"))
    monkeypatch.setattr(visual, "analyze", fake_an)
    return calls
GOOD = "Ingredients:\\n500 g chicken\\n2 tomatoes\\n200 g pasta\\n\\nMethod\\nCook"
VIS = lambda *a: {"title": "T", "servings": 2, "items": [{"line": "2 egg", "confidence": "confirmed", "seen_at": "00:42", "conflict": None},
        {"line": "Unidentified ingredient", "confidence": "uncertain", "seen_at": "01:04", "conflict": None}], "steps": ["Crack two eggs"], "partial": False,
        "source": "visual analysis (Gemini + Groq)", "visual": {"total": 2, "confirmed": 1, "estimated": 0, "uncertain": 1}}

def test_description_recipe_does_not_call_gemini(monkeypatch):
    calls = setup(monkeypatch, page(GOOD), True, VIS)
    r = run(extract.from_url(URL)); assert r["source"] == "YouTube description" and not calls
def test_transcript_recipe_does_not_call_gemini(monkeypatch):
    calls = setup(monkeypatch, page("Yum!"), True, VIS, tr="we need two eggs")
    async def fake(t): return {"servings": 2, "lines": ["2 eggs", "1 onion", "salt"]}
    monkeypatch.setattr(llm, "KEY", "k"); monkeypatch.setattr(llm, "extract_ingredients", fake)
    r = run(extract.from_url(URL)); assert "transcript" in r["source"] and not calls
def test_no_description_goes_visual(monkeypatch):
    calls = setup(monkeypatch, page(""), True, VIS); assert run(extract.from_url(URL))["visual"]["total"] == 2 and calls
def test_insufficient_description_goes_visual(monkeypatch):
    calls = setup(monkeypatch, page("Try this amazing crispy egg snack!"), True, VIS); assert run(extract.from_url(URL))["items"] and calls
def test_incomplete_text_supplemented(monkeypatch):
    calls = setup(monkeypatch, page("Ingredients:\\n2 eggs\\n1 onion"), True, VIS); assert run(extract.from_url(URL))["visual"] and calls
def test_incomplete_text_survives_gemini_failure(monkeypatch):
    setup(monkeypatch, page("Ingredients:\\n2 eggs\\n1 onion"), True, None)
    r = run(extract.from_url(URL)); assert r["source"] == "YouTube description" and "unavailable" in r["warning"]
def test_missing_gemini_key_keeps_old_behaviour(monkeypatch):
    calls = setup(monkeypatch, page("Ingredients:\\n2 eggs\\n1 onion"), False, VIS)
    assert run(extract.from_url(URL))["source"] == "YouTube description" and not calls
    setup(monkeypatch, page(""), False, VIS)
    with pytest.raises(extract.ExtractError, match="Couldn't get a recipe"): run(extract.from_url(URL))
def test_gemini_failure_does_not_fabricate(monkeypatch):
    setup(monkeypatch, page(""), True, None)
    with pytest.raises(extract.ExtractError, match="Unable to visually analyze"): run(extract.from_url(URL))
def test_invalid_urls_rejected():
    for u in ["ftp://x.com/a", "http://127.0.0.1/", "http://169.254.169.254/", "https://user@x.com"]:
        with pytest.raises(extract.ExtractError): run(extract.from_url(u))
def test_too_long_video(monkeypatch):
    monkeypatch.setattr(visual, "KEY", "k")
    with pytest.raises(visual.VisualError, match="longer"): run(visual.analyze("dQw4w9WgXcQ", page("", 99999), "1.1.1.1", "t"))
def test_visual_rate_limit_per_ip():
    visual._ip.clear()
    for _ in range(visual.PER_IP_HR): visual.check_quota("9.9.9.9")
    with pytest.raises(visual.VisualError, match="too many"): visual.check_quota("9.9.9.9")
    visual._ip.clear()

def test_observation_validation():
    o = visual.validate_obs({"observations": [{"timestamp": "00:42", "ingredient": "<b>egg</b>", "quantity": "2", "quantity_type": "observed", "confidence": 5, "evidence": "x"},
        {"timestamp": "bad", "ingredient": "oil", "quantity": "1 tbsp", "quantity_type": "unknown", "confidence": "?"}, "junk"]})
    assert o[0]["ingredient"] == "bEgg/bEgg"[:0] + "begg/b" and o[0]["confidence"] == 1.0 and o[1]["quantity"] is None and o[1]["timestamp"] is None and len(o) == 2
def test_unidentified_ingredient_and_quantity_never_invented():
    r = llm.validate_recipe({"ingredients": [{"name": "Unidentified ingredient", "quantity": "a handful of magic", "confidence": "bogus"},
        {"name": "egg", "quantity": "~1½ cup", "confidence": "estimated", "seen_at": "00:42"}, {"name": "see http://x.co"}], "steps": ["<i>Crack</i> eggs"]})
    a, b = r["ingredients"]
    assert a["name"] == "Unidentified ingredient" and a["quantity"] is None and a["confidence"] == "uncertain"
    assert b["quantity"] == "1 1/2 cup" and len(r["ingredients"]) == 2 and "<" not in r["steps"][0] and ">" not in r["steps"][0]
def test_groq_failure_in_reconcile(monkeypatch):
    async def boom(*a): raise RuntimeError("x")
    monkeypatch.setattr(llm, "reconcile", boom); monkeypatch.setattr(visual, "KEY", "k")
    async def obs(v, d): return [{"ingredient": "egg"}]
    monkeypatch.setattr(visual, "_observe", obs); visual._ip.clear(); visual._cache.clear()
    with pytest.raises(visual.VisualError, match="structured"): run(visual.analyze("dQw4w9WgXcQ", page(""), "2.2.2.2", "t"))
def test_ocr_conflict_preserved():
    r = llm.validate_recipe({"ingredients": [{"name": "chilli powder", "quantity": "1 tsp", "confidence": "estimated", "conflict": "text says 1 tsp, video shows ~2 tsp"}]})
    assert r["ingredients"][0]["conflict"].startswith("text says")
def test_api_returns_confidence_and_steps(monkeypatch):
    async def fake(u, ip="?"): return VIS()
    monkeypatch.setattr(extract, "from_url", fake)
    d = TestClient(main.app).post("/api/extract", json={"url": URL}).json()
    assert d["ingredients"][0]["confidence"] == "confirmed" and d["ingredients"][0]["seen_at"] == "00:42" and d["steps"] and d["visual"]["total"] == 2
def test_no_keys_in_frontend():
    t = "".join(open(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", f), encoding="utf-8").read() for f in ("app.js", "index.html", "config.js"))
    assert not re.search(r"gsk_|AIza|VITE_|GEMINI_API_KEY|GROQ_API_KEY", t)

# ---- Instamart pack-size handling: recipe need != retail pack ----
def P(i, q, price, u="g", name="Mayonnaise", brand="B", av=True):
    return dict(product_id=i, name=name, brand=brand, category=None, variant=None, pack_quantity=q, pack_unit=u, price=price, availability=av, image_url=None)
def R(n, q, u): return dict(requirement_id="r1", ingredient_name=n, normalized_name=n, required_quantity=q, unit=u, category=None, optional=False, notes=None)
def L(r): return sorted((l["product"]["product_id"], l["packs"]) for l in r["selection"])

def test_small_need_picks_smallest_real_pack_and_keeps_data():
    ps = [P("a", 100, 40), P("b", 250, 80), P("c", 500, 140)]
    r = e.solve(R("mayonnaise", 30, "g"), ps)
    assert L(r) == [("a", 1)] and r["selection"][0]["product"] == ps[0] and r["excess"] == 70
    assert len(r["candidates"]) == 3  # all real pack options remain visible
def test_tbsp_mayo_converted_with_original_shown():
    r = e.solve(R("mayonnaise", 30, "ml"), [P("a", 250, 80)])
    assert r["requirement"]["unit"] == "g" and r["requirement"]["original"] == "30 ml" and L(r) == [("a", 1)]
def test_only_larger_pack_available():
    assert L(e.solve(R("salt", 3, "ml"), [P("s", 1000, 25, name="Salt", brand="Tata")])) == [("s", 1)]
def test_oil_liquid_and_repeated_total():
    rq = e.make_requirements([e.parse_line("1 tbsp oil"), e.parse_line("2 tbsp oil")], {})
    assert len(rq) == 1 and rq[0]["required_quantity"] == 45
    assert L(e.solve(rq[0], [P("o", 1000, 150, "ml", "Sunflower Oil")])) == [("o", 1)]
def test_count_based_vs_weight_pack_not_pretended():
    r = e.solve(R("tomato", 1, "piece"), [P("t", 500, 30, name="Fresh Tomato")])
    assert r["unverified"] and L(r) == [("t", 1)] and r["purchased"] is None and any(x.startswith("⚠") for x in r["reasons"])
def test_unavailable_and_no_product():
    assert e.solve(R("mayonnaise", 30, "g"), [P("a", 100, 40, av=False)])["status"] == "no_match"
def test_multiple_brands_price_preserved():
    ps = [P("a", 100, 49.5, brand="X"), P("b", 100, 45.25, brand="Y")]
    r = e.solve(R("mayonnaise", 30, "g"), ps); s = r["selection"][0]["product"]
    assert s["brand"] == "Y" and s["price"] == 45.25 and s["pack_quantity"] == 100 and s["pack_unit"] == "g"
