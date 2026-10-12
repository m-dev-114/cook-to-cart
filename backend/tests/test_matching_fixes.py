import asyncio, pathlib, pytest
import engine as e

APP = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "app.js").read_text(encoding="utf-8")


def P(pid, name, q=100, u="g", price=20, avail=True):
    return dict(product_id=pid, name=name, brand=None, variant=None, pack_quantity=q, pack_unit=u, pack_label=f"{q} {u}", price=price, availability=avail)


def R(line):
    i = e.parse_line(line); return e.make_requirements([i], {i["name"]: "buy"})[0]


# ---- parsing ----
@pytest.mark.parametrize("line,q,u,nn", [("ONION 1/2 KG", 500, "g", "onion"), ("CORIANDER SEEDS 2 TBSP", None, None, "coriander seed"),
                                         ("BLACK CARDAMOM 5-6 NOS", 6, "piece", "black cardamom"), ("CINNAMON 3 INCH", 24, "g", "cinnamon")])
def test_amount_last_lines(line, q, u, nn):
    p = e.parse_line(line); assert p["normalized_name"] == nn
    if q is not None: assert (p["quantity"], p["unit"]) == (q, u)
    assert p["original_text"] == line and p["canonical_name"]
    assert not any(ch.isdigit() for ch in p["normalized_name"])


def test_search_terms_have_no_quantities():
    for line in ["ONION 1/2 KG", "BLACK CARDAMOM 5-6 NOS", "CINNAMON 3 INCH", "2 tbsp coriander seeds"]:
        for t in e.search_terms(R(line)): assert not any(c.isdigit() for c in t) and not {"kg", "nos", "inch", "tbsp"} & set(t.split()), t


# ---- aliases ----
def test_cilantro_is_coriander_leaves():
    assert e.canon("cilantro") == "fresh coriander"
    r = R("1 bunch cilantro"); sc, why, sub = e.score(r, P("a", "Fresh Coriander Leaves"))
    assert sc > 0 and not sub and why[0].startswith("Also sold as")
    assert "coriander leaf" in e.search_terms(r)


def test_leaves_seeds_powder_not_confused():
    leaves = R("1 bunch cilantro")
    for bad in ["Coriander Powder", "Coriander Seeds", "Dhania Powder"]: assert e.score(leaves, P("x", bad))[0] == 0, bad
    seeds = R("2 tbsp coriander seeds")
    assert e.score(seeds, P("x", "Coriander Leaves"))[0] == 0 and e.score(seeds, P("y", "Coriander Seeds"))[0] > 0


def test_cumin_not_caraway_and_cardamom_colours():
    cumin = R("1 tsp cumin seeds")
    assert e.score(cumin, P("a", "Jeera (Cumin Seeds)"))[0] > 0 and e.score(cumin, P("b", "Shahi Jeera Caraway Seeds"))[0] == 0
    green = R("4 green cardamom"); assert e.score(green, P("a", "Black Cardamom Badi Elaichi"))[0] == 0
    bare = R("4 cardamom"); sc, _, sub = e.score(bare, P("a", "Black Cardamom")); assert sub  # needs approval, not exact


def test_salt_vs_black_salt_and_onion_variety_and_yogurt():
    salt = R("1 tsp salt")
    r = e.solve(salt, [P("b", "Black Salt (Kala Namak)", 100, "g", 10), P("s", "Iodised Crystal Salt", 1000, "g", 25)])
    assert r["selection"][0]["product"]["product_id"] == "s" and r["outcome"] == "exact"
    assert e.solve(salt, [P("b", "Black Salt", 100, "g", 10)])["status"] == "needs_substitute_approval"
    assert e.solve(R("1 onion"), [P("o", "Sambar Onion", 500, "g")])["status"] == "needs_substitute_approval"
    assert e.score(R("200 g yogurt"), P("f", "Strawberry Flavoured Yogurt", 200, "g"))[0] == 0


def test_alias_not_exact_wording():
    r = e.solve(R("2 tbsp haldi"), [P("t", "Turmeric Powder", 100, "g")])
    assert r["status"] == "ok" and r["outcome"] == "alias_equivalent"
    assert "Lowest-cost valid combination" not in " ".join(r["reasons"])


# ---- search status / coverage ----
def test_failed_vs_missing_vs_unavailable():
    req = R("1 tsp cumin seeds")
    f = e.failed_result(req); assert f["status"] == "search_failed"
    assert e.solve(req, [])["outcome"] == "no_suitable_product"
    cv = e.coverage([f, e.solve(req, [])], [], []); assert [r["state"] for r in cv["rows"]] == ["search_failed", "missing"]
    assert cv["counts"]["unresolved"] == 2


def test_coverage_counts_skipped_not_covered():
    ok = e.solve(R("1 tsp cumin seeds"), [P("c", "Cumin Seeds", 100, "g")])
    cv = e.coverage([ok], [{"name": "salt", "status": "full"}], ["pepper", "oregano"])
    base = {"to_buy": 1, "selected": 1, "pantry": 1, "verified": 0, "estimated": 1, "unverified": 0, "skipped": 2, "unresolved": 0}
    assert {k: cv["counts"][k] for k in base} == base and cv["counts"]["exact"] == 1 and cv["counts"]["unavailable"] == 0
    assert cv["covered"] == 2 and all(r["state"] == "skipped" for r in cv["rows"] if r["name"] in ("pepper", "oregano"))


# ---- search retries / dedupe ----
class FakeClient:
    label = "t"
    def __init__(s, table, fail=()): s.table, s.fail, s.calls = table, set(fail), []
    async def search(s, q, a, sid):
        import swiggy
        s.calls.append(q)
        if q in s.fail: raise swiggy.SwiggyError("boom")
        return [dict(p) for p in s.table.get(q, [])]


def test_search_retries_aliases_and_merges(monkeypatch):
    import main
    fc = FakeClient({"coriander leaf": [P("a", "Coriander Leaves", 100, "g", 10), P("a", "Coriander Leaves", 100, "g", 10)], "dhania": [P("a", "Coriander Leaves", 100, "g", 10)]})
    monkeypatch.setattr(main, "client", fc)
    ps, err = asyncio.run(main._search_req(R("1 bunch cilantro"), "addr", "s"))
    assert err is None and [p["product_id"] for p in ps] == ["a"] and fc.calls[0] == "cilantro" and "coriander leaf" in fc.calls


def test_every_query_failing_is_search_failed(monkeypatch):
    import main
    r = R("1 bunch cilantro"); fc = FakeClient({}, fail=set(e.search_terms(r)))
    monkeypatch.setattr(main, "client", fc)
    ps, err = asyncio.run(main._search_req(r, "addr", "s")); assert ps == [] and err is not None


def test_swiggy_search_dedupes_listings():
    import swiggy
    c = swiggy.SwiggyInstamartMCPClient.__new__(swiggy.SwiggyInstamartMCPClient); c.seen = {}
    v = {"spinId": "1", "skuId": "k1", "quantityDescription": "100 g", "price": {"offerPrice": 10}, "isInStockAndAvailable": True}
    async def call(sid, tool, args, confirmed=False): return {"products": [{"displayName": "Coriander", "variations": [v, {**v, "spinId": "2", "skuId": "k2"}]}]}
    c.call = call
    out = asyncio.run(c.search("coriander", "addr", "s")); assert len(out) == 1


# ---- frontend null safety ----
def test_frontend_never_renders_null_text():
    assert "Element.prototype.replaceChildren=function" in APP and "x!=null&&x!==false" in APP
    assert 'money=n=>n==null' in APP
    assert 'r.verified===true' in APP and "NOT verified" in APP
