"""Evaluation of the full pipeline (parse -> interpret -> retrieve -> validate -> rank -> quantity) on MOCKED live-shaped catalogs.
Run:  python -m eval.run_eval        (from backend/). Reports metrics; it never claims universal accuracy."""
import asyncio, os, sys, time, json, statistics
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import engine, retrieval, understand, swiggy
from eval.catalog import CATALOG, search
from eval.dataset import RECIPES


class MockClient:
    def __init__(s, fail=(), out=()): s.fail, s.out, s.calls = set(fail), set(out), 0
    async def search(s, q, addr=None, sid="eval"):
        s.calls += 1
        if "*" in s.fail or q in s.fail: raise swiggy.SwiggyError("injected", "MCP_TIMEOUT")
        return search(q, unavailable=s.out)


async def run_recipe(name, rows, chat=None, fail=()):
    ings = [engine.parse_line(r[0]) for r in rows]
    reqs = engine.make_requirements(ings, {}); by = {i["normalized_name"]: i for i in ings}
    profs = await understand.interpret([by[r["normalized_name"]] for r in reqs], chat=chat)
    for r, p in zip(reqs, profs): r["interp"] = understand.for_requirement(p)
    cl = MockClient(fail=fail); res = []
    for r, p in zip(reqs, profs):
        t0 = time.perf_counter(); ps, err = await retrieval.retrieve(cl, r, "a", "eval")
        out = engine.failed_result(r) if err and not ps else engine.solve(r, ps)
        res.append((r, p, out, time.perf_counter() - t0))
    return res, cl


async def evaluate(chat=None, verbose=False):
    m = dict(n=0, interp_ok=0, interp_n=0, expect_exact=0, retrieved=0, auto_ok=0, selections=0, wrong_exact=0, forbidden_n=0, forbidden_labelled=0, none_n=0, none_ok=0, qty_n=0, qty_ok=0, dup_lines=0, lines=0, fails=0)
    lat, rows_out = [], []
    for name, rows in RECIPES.items():
        res, cl = await run_recipe(name, rows, chat)
        cart = []
        for (line, expect, allowed, forb, hint), (r, p, out, dt) in zip(rows, res):
            m["n"] += 1; lat.append(dt)
            m["interp_n"] += 1; txt = " ".join([p["canonical"] or ""] + p["queries"] + p["aliases"] + engine.search_terms(r))
            ok_i = hint.lower() in txt.lower(); m["interp_ok"] += ok_i
            ids = {c["product"]["product_id"] for c in out["candidates"]}; sel = [l["product"]["product_id"] for l in out["selection"]]
            if out["status"] == "search_failed": m["fails"] += 1
            if expect == "exact":
                m["expect_exact"] += 1; m["retrieved"] += bool(ids & allowed); m["auto_ok"] += bool(set(sel) & allowed)
            if expect == "none": m["none_n"] += 1; m["none_ok"] += (not sel)
            m["selections"] += bool(sel); wrong = bool(sel) and not (set(sel) & allowed); m["wrong_exact"] += wrong
            if forb:
                m["forbidden_n"] += 1; m["forbidden_labelled"] += any(c["product"]["product_id"] in forb and c["match"] in ("EXACT_MATCH", "VALID_VARIANT") for c in out["candidates"])
            if sel and out.get("covers") is not None: m["qty_n"] += 1; m["qty_ok"] += bool(out["covers"])
            cart += sel
            if verbose and (wrong or (expect == "exact" and not (set(sel) & allowed)) or not ok_i):
                rows_out.append((name, line, out["status"], [c["product"]["name"] + ":" + c["match"] for c in out["candidates"]][:3], sel, "interp" if not ok_i else ""))
        m["lines"] += len(cart); m["dup_lines"] += len(cart) - len(set(cart))
    pct = lambda a, b: round(100 * a / b, 1) if b else None
    rep = {"ingredients": m["n"], "recipes": len(RECIPES), "interpretation_accuracy_%": pct(m["interp_ok"], m["interp_n"]), "suitable_product_retrieval_%": pct(m["retrieved"], m["expect_exact"]),
           "auto_selected_correctly_%": pct(m["auto_ok"], m["expect_exact"]), "incorrect_exact_match_rate_%": pct(m["wrong_exact"], m["selections"]),
           "forbidden_product_labelled_exact_or_suitable_%": pct(m["forbidden_labelled"], m["forbidden_n"]), "unavailable_not_auto_selected_%": pct(m["none_ok"], m["none_n"]),
           "selected_pack_covers_requirement_%": pct(m["qty_ok"], m["qty_n"]), "duplicate_cart_line_rate_%": pct(m["dup_lines"], m["lines"]), "search_failures": m["fails"],
           "latency_ms_p50": round(1000 * statistics.median(lat), 2), "latency_ms_p95": round(1000 * sorted(lat)[int(0.95 * (len(lat) - 1))], 2)}
    return rep, rows_out


if __name__ == "__main__":
    rep, bad = asyncio.run(evaluate(verbose=True)); print(json.dumps(rep, indent=1))
    for b in bad: print(b)
