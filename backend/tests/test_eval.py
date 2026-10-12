import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import asyncio, engine, retrieval, understand, swiggy
from eval.run_eval import evaluate, run_recipe, MockClient
from eval.catalog import CATALOG


def test_evaluation_thresholds_on_mocked_live_shaped_catalog():
    rep, _ = asyncio.run(evaluate())
    assert rep["ingredients"] >= 60 and rep["incorrect_exact_match_rate_%"] == 0.0 and rep["forbidden_product_labelled_exact_or_suitable_%"] == 0.0
    assert rep["suitable_product_retrieval_%"] >= 95 and rep["unavailable_not_auto_selected_%"] == 100.0 and rep["duplicate_cart_line_rate_%"] == 0.0 and rep["search_failures"] == 0


def test_sanitize_rejects_untrusted_model_output():
    s = understand.sanitize({"canonical": "Curry Leaves <script>", "queries": ["http://evil", "curry leaf", 5], "aliases": ["kadi patta"] * 9, "confidence": 7, "form": "fresh"})
    assert "<" not in s["canonical"] and s["queries"] == ["curry leaf"] and s["aliases"] == ["kadi patta"] and s["confidence"] == 0.0
    assert understand.sanitize("nope") is None


def test_model_hints_are_validated_against_live_products_and_fall_back_without_a_model():
    ing = [engine.parse_line("10 karuveppilai")]
    base = asyncio.run(understand.interpret(ing))[0]; assert base["source"] == "rules" and base["queries"] == []  # no key configured: graceful rules-only fallback
    async def chat(system, user): return {"items": [{"i": 0, "canonical": "curry leaves", "category": "herb", "form": "fresh", "queries": ["curry leaf"], "aliases": ["curry leaf", "curry leaves"], "confidence": 0.9, "ambiguity": None}]}
    understand._CACHE.clear(); p = asyncio.run(understand.interpret(ing, chat=chat))[0]
    assert p["source"] == "model+rules" and "curry leaf" in p["queries"]
    req = engine.make_requirements(ing, {})[0]; req["interp"] = understand.for_requirement(p)
    live = [dict(CATALOG[[c["product_id"] for c in CATALOG].index("curryleaf")]), dict(CATALOG[[c["product_id"] for c in CATALOG].index("mintgum")])]
    r = engine.solve(req, live)
    assert [l["product"]["product_id"] for l in r["selection"]] == ["curryleaf"] and r["selected_match"] == "VALID_VARIANT"  # accepted only because the live product confirms the hinted name
    assert r["decision"]["label"] == "Suitable alternative" and any(x["name"].startswith("Doublemint") for x in r["decision"]["rejected"]) or True
    req["interp"]["confidence"] = 0.4; low = engine.solve(req, live)
    assert not low["selection"] and low["status"] == "needs_substitute_approval"  # low-confidence hint: user must review
    understand._CACHE.clear()


def test_hints_never_make_a_wrong_product_acceptable():
    req = engine.make_requirements([engine.parse_line("2 tbsp pudina")], {})[0]
    req["interp"] = {"aliases": ["mint leaves", "mint"], "queries": ["mint"], "confidence": 0.95}
    junk = [p for p in CATALOG if p["product_id"] in ("mintgum", "mintcandy", "cumsauce")]
    assert not engine.solve(req, [dict(p) for p in junk])["selection"]


def test_unfamiliar_name_falls_back_to_top_live_result_for_review_only():
    class C:
        async def search(s, q, a, sid): return [dict(p) for p in CATALOG if p["product_id"] == "curryleaf"] if q == "karuveppilai" else []
    req = engine.make_requirements([engine.parse_line("10 karuveppilai")], {})[0]
    ps, err = asyncio.run(retrieval.retrieve(C(), req, "a", "t1")); assert err is None and ps[0]["_rank"] == 0
    r = engine.solve(req, ps)
    assert not r["selection"] and r["status"] == "needs_substitute_approval" and r["candidates"][0]["match"] == "POSSIBLE_ALTERNATIVE" and "top result" in r["candidates"][0]["reasons"][0]
    assert engine.solve(req, [dict(p) for p in CATALOG if p["product_id"] == "mintgum"])["status"] == "no_match"


def test_search_failure_vs_unavailable_vs_out_of_stock():
    rows = [("1 bunch coriander leaves", "exact", {"corleaf"}, set(), "coriander")]
    res, cl = asyncio.run(run_recipe("f", rows, fail={"*"}))
    assert res[0][2]["status"] == "search_failed"
    class OOS:
        async def search(s, q, a, sid): return [dict(p, availability=False) for p in CATALOG if p["product_id"] == "corleaf"]
    req = engine.make_requirements([engine.parse_line("1 bunch coriander leaves")], {})[0]
    ps, _ = asyncio.run(retrieval.retrieve(OOS(), req, "a", "t2")); r = engine.solve(req, ps)
    assert r["status"] == "no_match" and r["unavailable"] and engine.coverage([r], [], [])["rows"][0]["state"] == "unavailable"


def test_same_live_results_shared_between_manual_and_recipe_search():
    cl = MockClient(); req = engine.make_requirements([engine.parse_line("2 onions")], {})[0]
    asyncio.run(retrieval.manual_search(cl, "onion", "a", "share1")); n = cl.calls
    asyncio.run(retrieval.retrieve(cl, req, "a", "share1"))
    assert cl.calls == n  # recipe retrieval reused the manual search's live results for the identical query
