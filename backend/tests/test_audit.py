import pathlib, asyncio
import engine as e, swiggy

APP = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "app.js").read_text(encoding="utf-8")


def P(pid, name, q=100, u="g", price=20, avail=True):
    return dict(product_id=pid, name=name, brand=None, variant=None, pack_quantity=q, pack_unit=u, pack_label=f"{q} {u}", price=price, availability=avail)


def run(line, prods, **k):
    i = e.parse_line(line); return e.solve(e.make_requirements([i], {i["name"]: "buy"})[0], prods, **k)


# ---- addresses ----
ID = "d80auakorulq5fj62i50__AMVGbgShgIcxlZe1wktAqq"
def test_address_never_shows_opaque_id():
    for a in [{"id": ID}, {"id": ID, "address": ID}, {"id": ID, "addressId": ID, "displayAddress": {"line": ID}}, {"id": ID, "area": f"Near {ID}"}]:
        assert ID not in swiggy.fmt_address(a) and "d80auakorulq5fj62i50" not in swiggy.fmt_address(a)
def test_address_readable_fields_and_nested():
    assert swiggy.fmt_address({"id": ID, "tag": "HOME", "address": "12 MG Road", "city": "Port Blair"}) == "HOME: 12 MG Road, Port Blair"
    assert "Sector 5" in swiggy.fmt_address({"id": ID, "annotation": "Work", "location": {"area": "Sector 5"}})
    assert swiggy.fmt_address({"id": ID}).startswith("Saved address 1")  # incomplete address: honest fallback, id hidden
def test_addresses_multiple_and_empty():
    c = swiggy.SwiggyInstamartMCPClient.__new__(swiggy.SwiggyInstamartMCPClient)
    async def call(sid, tool, args, confirmed=False): return {"addresses": [{"id": "a1", "tag": "Home", "address": "1 A St"}, {"id": "a2"}, {"noid": 1}]}
    c.call = call; out = asyncio.run(c.addresses("s")); assert [a["id"] for a in out] == ["a1", "a2"] and out[0]["label"] == "Home: 1 A St"
    async def empty(sid, tool, args, confirmed=False): return {"addresses": []}
    c.call = empty; assert asyncio.run(c.addresses("s")) == []


# ---- matching ----
def test_user_cases_from_live_biryani_run():
    assert run("1/2 kg onion", [P("a", "Organic Certified Onion Sambhar", 250), P("b", "Peeled Sambhar Onion", 200)])["status"] == "needs_substitute_approval"
    r = run("3 inch cinnamon", [P("p", "Snapin Cinnamon Powder", 45, price=10), P("w", "Cinnamon Whole (Dalchini)", 25, price=29)])
    assert r["selection"][0]["product"]["product_id"] == "w"
    assert {c["product"]["product_id"]: c["match"] for c in r["candidates"]}["p"] == "POSSIBLE_ALTERNATIVE"
    r = run("8 Spicy Red Chillies", [P("a", "Chilli Whole With Stem", 50), P("g", "Green Chilli", 100, price=1), P("s", "Red Chilli Sauces", 90, price=1), P("f", "Snapin Chilli Flakes Sachet", 10, price=1), P("m", "Mtr Chilli Powder", 100, price=1)])
    assert r["status"] == "ok" and r["selection"][0]["product"]["product_id"] == "a"
def test_ghee_butter_coconut_milk_cream_chicken_liver_leaves_seeds():
    assert run("1 tbsp ghee", [P("b", "Salted Butter", 100)])["status"] != "ok"
    assert run("200 ml coconut milk", [P("c", "Coconut Cream", 200, "ml")])["status"] != "ok"
    assert run("500 g chicken", [P("l", "Chicken Liver", 500)])["status"] == "no_match"
    assert run("2 tbsp coriander seeds", [P("l", "Fresh Coriander Leaves", 100)])["status"] == "no_match"
def test_accepted_substitute_label():
    r = run("1 onion", [P("o", "Sambar Onion", 500)], approved=True)
    assert r["status"] == "ok" and r["candidates"][0]["match"] == "USER_ACCEPTED_SUBSTITUTION"


# ---- quantities / honesty ----
def test_spoon_and_piece_amounts_converted_with_estimate_flag():
    r = run("2 tbsp green cardamom", [P("g", "Green Cardamom", 25, price=100)])
    assert r["status"] == "ok" and r["estimated"] is True and r["requirement"]["unit"] == "g"
    r = run("6 pieces black cardamom", [P("b", "Black Cardamom Whole", 20, price=70)])
    assert r["estimated"] is True and not r["unverified"]
def test_unknown_conversion_is_not_claimed_as_covered():
    r = run("3 pieces zzzfruit", [P("z", "Zzzfruit Pack", 250, price=50)])
    assert r["unverified"] is True and r["excess"] is None
    cv = e.coverage([r], [], []); assert cv["rows"][0]["state"] == "assumed" and cv["counts"]["verified"] == 0 and cv["counts"]["unverified"] == 1
def test_selected_is_not_verified_in_counts():
    ok = run("100 g cumin seeds", [P("c", "Cumin Seeds", 100)]); un = run("3 pieces zzzfruit", [P("z", "Zzzfruit Pack", 250)])
    n = e.coverage([ok, un], [], [])["counts"]; assert (n["selected"], n["verified"], n["estimated"], n["unverified"], n["to_buy"]) == (2, 1, 0, 1, 2)
def test_servings_scaling_keeps_units():
    i = e.scale_ings([e.parse_line("2 tbsp coriander seeds")], 4, 8)[0]
    assert i["source_quantity"] == 4 and i["quantity"] == 2 * e.parse_line("2 tbsp coriander seeds")["quantity"]


# ---- incomplete extraction ----
def test_biryani_without_rice_or_chicken_is_flagged():
    ings = [e.parse_line(l) for l in ["1 tsp cumin seeds", "2 tbsp coriander seeds", "1 tsp turmeric powder", "Salt"]]
    names = [m["name"] for m in e.missing_essentials("Chicken Dum Biryani Recipe", ings)]
    assert "rice" in names and "chicken" in names
def test_complete_recipe_not_flagged():
    ings = [e.parse_line(l) for l in ["500 g chicken", "2 cups basmati rice", "1 tsp salt"]]
    assert e.missing_essentials("Chicken Biryani", ings) == []
def test_extract_endpoint_returns_suggestions():
    from fastapi.testclient import TestClient
    import main
    r = TestClient(main.app).post("/api/extract", json={"text": "Chicken Dum Biryani\n1 tsp cumin seeds\n2 tbsp coriander seeds\n1 tsp salt\n1 tsp turmeric powder"}).json()
    assert {m["name"] for m in r["suggested_missing"]} == {"rice", "chicken"}


# ---- frontend consistency ----
def test_frontend_uses_one_count_source_and_no_false_cover_claim():
    assert "cov.counts.selected" in APP and "estimated · " in APP and "cov.covered+" not in APP
    assert "1 pack assumed: can't verify" in APP and "suggested_missing" in APP and "estimated conversion" in APP


# ---- create_address / bill / mic removal ----
def _client(resp):
    c = swiggy.SwiggyInstamartMCPClient.__new__(swiggy.SwiggyInstamartMCPClient); c.seen, c.cart_addr, c.totals, c.bills, calls = {}, {}, {}, {}, []
    async def call(sid, tool, args, confirmed=False): calls.append((tool, args, confirmed)); return resp(tool)
    c.call = call; c.calls = calls; return c
BODY = {"confirm": True, "fullAddress": "12 MG Road, Port Blair 744101", "addressLine": "12 MG Road", "addressLine2": "", "city": "Port Blair", "postalCode": "744101", "addressCategory": "HOME", "userName": "Dev", "userPhone": "9876543210"}
def test_create_address_endpoint_uses_documented_params_and_verifies(monkeypatch):
    from fastapi.testclient import TestClient
    import main
    c = _client(lambda t: {"addressId": "new1"} if t == "create_address" else {"addresses": [{"id": "new1", "addressLine": "12 MG Road", "addressTag": "Home"}]})
    monkeypatch.setattr(main, "client", c); tc = TestClient(main.app, headers={"X-Session": "addr-test-1"})
    r = tc.post("/api/instamart/address/create", json=BODY); assert r.status_code == 200 and r.json()["address_id"] == "new1"
    tool, args, conf = c.calls[0]; assert tool == "create_address" and conf and "confirm" not in args and set(args) <= {"fullAddress", "addressLine", "addressLine2", "locality", "city", "postalCode", "latitude", "longitude", "addressCategory", "addressTag", "userName", "userPhone", "receiverName", "receiverPhone"}
def test_create_address_requires_confirm_and_valid_input(monkeypatch):
    from fastapi.testclient import TestClient
    import main
    tc = TestClient(main.app, headers={"X-Session": "addr-test-2"})
    assert tc.post("/api/instamart/address/create", json={**BODY, "confirm": False}).status_code == 400
    assert tc.post("/api/instamart/address/create", json={**BODY, "addressCategory": "HACK"}).status_code == 422
    assert tc.post("/api/instamart/address/create", json={**BODY, "userPhone": "abc"}).status_code == 422
def test_create_address_not_confirmed_by_swiggy_is_error(monkeypatch):
    import pytest
    c = _client(lambda t: {})
    with pytest.raises(swiggy.SwiggyError): asyncio.run(c.create_address("s", {"city": "x"}))
def test_bill_breakdown_parsed_without_assuming_label_names():
    c = _client(lambda t: {"cartTotalAmount": "300", "items": [], "billBreakdown": {"lineItems": [{"label": "Item total", "value": "₹291"}, {"label": "Handling", "value": "₹9"}], "toPay": {"label": "To pay", "value": "₹1,300.50"}}})
    asyncio.run(c.get_cart("s")); b = c.bills["s"]; assert b["to_pay_amount"] == 1300.5 and [l["label"] for l in b["lines"]] == ["Item total", "Handling"]
def test_missing_bill_is_none_not_zero():
    c = _client(lambda t: {"cartTotalAmount": "0", "items": [], "cartAbsent": True}); asyncio.run(c.get_cart("s")); assert c.bills["s"] is None
def test_create_address_is_the_only_new_mutating_tool_and_checkout_blocked():
    assert swiggy.CONFIRM == {"update_cart", "clear_cart", "create_address"}
    import pytest
    c = _client(lambda t: {})
    for t in ("checkout", "confirm_order", "place_order", "get_payment_options"):
        with pytest.raises(PermissionError): asyncio.run(swiggy.SwiggyInstamartMCPClient.call(c, "s", t, {}, confirmed=True))
def test_mic_removed():
    idx = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "mic" not in idx.lower().replace("atomic", "") and "SpeechRecognition" not in APP and 'id="mic"' not in idx


# ---- issues seen in the second live run ----
def test_spoon_conversion_counts_as_estimated_not_verified():
    n = e.coverage([run("1 tsp cumin seeds", [P("c", "Cumin Seeds", 100)])], [], [])["counts"]; assert (n["verified"], n["estimated"]) == (0, 1)
def test_no_browser_dialogs_used():
    import re
    assert not re.search(r"(?<![\w.])(prompt|confirm|alert)\(", APP.replace("async()=>", "")), "window.prompt/confirm/alert are unsupported in some browsers"
def test_address_label_has_no_duplicate_tag():
    assert swiggy.fmt_address({"id": "x1", "addressTag": "Demo", "addressLine": "Demo: 1st Floor, Swiggy HO, Bengaluru"}) == "Demo: 1st Floor, Swiggy HO, Bengaluru"
def test_suggestion_title_is_ascii_and_short():
    ings = [e.parse_line("1 tsp salt")]
    r = e.missing_essentials("Chicken Dum Biryani Recipe | \u0938\u094d\u0935\u093e\u0926\u093f\u0937\u094d\u091f | Chef Sanjyot Keer", ings)
    assert r and all("|" not in m["reason"] and "Chef" not in m["reason"] for m in r)
def test_as_needed_lines_are_reported_as_skipped():
    from fastapi.testclient import TestClient
    import main
    ings = [e.parse_line("Salt"), e.parse_line("1 tsp cumin seeds")]
    r = TestClient(main.app).post("/api/shopping-requirements", json={"ingredients": ings, "pantry": {"Salt": "skip"}}).json()
    assert r["skipped"] == ["Salt"]
def test_best_fit_prefers_exact_over_cheaper_alias():
    r = e.solve(e.make_requirements([e.parse_line("3 inch cinnamon")], {"Cinnamon": "buy"})[0], [P("e", "Cinnamon Whole (Dalchini)", 25, price=35), P("c", "Cassia (Taj) Split", 25, price=29)])
    assert r["selection"][0]["product"]["product_id"] == "e"


# ---- cart visibility ----
def test_update_cart_response_adjustments_are_captured():
    c = _client(lambda t: {"removedOutOfStockItems": [{"itemName": "Mace"}], "reducedQuantityItems": [{"spinId": "1", "itemName": "Salt", "requestedQuantity": 5, "cappedQuantity": 2, "reason": "limit"}]})
    c.adjust = {}; c.seen = {("s", "p1"): {"sku_id": "k1"}}
    asyncio.run(c.update_cart("s", [{"product_id": "p1", "packs": 1}], "addr1"))
    assert c.adjust["s"]["removed"] == ["Mace"] and c.adjust["s"]["reduced"][0]["capped"] == 2
    assert c.calls[0][1] == {"selectedAddressId": "addr1", "items": [{"spinId": "p1", "skuId": "k1", "quantity": 1}]} and c.calls[0][2] is True
def test_success_message_names_the_address():
    assert "Swiggy carts are per address" in APP and "r.adjustments" in APP and "cart_address_matches" in APP


# ---- third live run: wrong products, stale cart hash, address first ----
def test_chicken_never_matches_processed_chicken_products():
    for nm in ["Chicken Reshmi Kebab", "Chicken Tikka", "Chicken Seekh Kebab", "Chicken Popcorn", "Chicken Nuggets", "Chicken Biryani Masala"]:
        assert e.score(e.make_requirements([e.parse_line("500 g chicken")], {"chicken": "buy"})[0], P("a", nm, 200))[0] == 0, nm
    assert e.score(e.make_requirements([e.parse_line("500 g chicken")], {"chicken": "buy"})[0], P("a", "Chicken Curry Cut Fresh", 500))[0] > 0
def test_mint_leaves_never_match_mint_sweets():
    r = e.make_requirements([e.parse_line("1 piece mint leaves")], {"mint leaves": "buy"})[0]
    for nm in ["Doublemint Peppermint Flavour Chewy Mint", "Mint Candy", "Polo Mints"]: assert e.score(r, P("a", nm, 3))[0] == 0, nm
    assert e.score(r, P("b", "Mint Leaves (Pudina)", 100))[0] > 0
def test_bare_coriander_is_found_for_coriander_leaves_but_not_seeds():
    r = e.make_requirements([e.parse_line("1 bunch coriander leaves")], {"coriander leaves": "buy"})[0]
    assert e.score(r, P("a", "Coriander", 100))[0] > 0 and e.score(r, P("b", "Coriander Seeds", 100))[0] == 0 and e.score(r, P("c", "Coriander Powder", 100))[0] == 0
def test_tap_water_is_never_a_shopping_requirement():
    for w in ["600 ml water", "1 cup warm water", "2 cups hot water"]:
        i = e.parse_line(w); assert e.make_requirements([i], {i["name"]: "buy"}) == [], w
    assert len(e.make_requirements([e.parse_line("2 tbsp coconut water")], {"coconut water": "buy"})) == 1
def test_cart_fingerprint_ignores_prices_and_names():
    import main
    a = [{"product_id": "p", "packs": 1, "price": 10, "name": "A"}]; b = [{"product_id": "p", "packs": 1, "price": 12, "name": "A (x)"}]
    assert main.chash(a) == main.chash(b) and main.chash(a) != main.chash([{"product_id": "p", "packs": 2}]) and main.chash([]) == main.chash([])
def test_stale_hash_returns_cart_changed_with_fresh_hash():
    from fastapi.testclient import TestClient
    import main
    c = TestClient(main.app, headers={"X-Session": "stale-hash-01"})
    r = c.post("/api/instamart/cart", json={"items": [{"product_id": "may-a1", "packs": 1}], "confirm": True, "expected_cart_hash": "stale", "idempotency_key": "stale-key-0001"})
    d = r.json(); assert r.status_code == 409 and d["code"] == "CART_CHANGED" and d["status"] == "FAILED_BEFORE_MUTATION" and d["hash"] == c.get("/api/instamart/cart").json()["hash"]
def test_address_comes_first_and_gates_extraction():
    idx = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "index.html").read_text(encoding="utf-8")
    assert idx.index('id="addrbox"') < idx.index('id="q"')
    assert 'S.mode==="swiggy"&&!S.addrOk)return problem("Choose your delivery address first, then extract' in APP and 'e.data.code==="CART_CHANGED"' in APP


# ---- visual QA regressions ----
def test_live_banner_is_only_shown_in_live_mode_and_placeholders_are_sized():
    assert 'if(S.mode==="swiggy"){$("banner").className="pill";' in APP  # braces: the LIVE pill must never appear in demo mode
    assert "DEMO MODE" in APP and "ph(c)" in APP and APP.count(":ph()") == 0
def test_serves_line_is_not_an_ingredient():
    for l in ["Serves 4", "Servings: 6", "Yield 12 cookies", "Prep time 10 min"]: assert e.parse_line(l) is None, l
def test_review_step_has_cost_summary_without_invented_fees():
    assert "Cost summary" in APP and "They are not estimated" in APP


# ---- visual QA pass ----
def test_visual_qa_layout_rules_present():
    idx = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'class="how"' in idx and "grid-column:2;grid-row:1/span 40;position:sticky" in idx and "repeat(2,minmax(0,1fr))" in idx
    assert "No image" not in APP and 'class:"issues"' in APP
def test_pasted_recipe_is_not_called_video_information():
    assert "Recipe extracted from video information" not in APP
