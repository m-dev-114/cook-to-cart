import sys, os, asyncio; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import engine as e, instamart

C = instamart.LocalInstamartMCPClient()
def req(line): return e.make_requirements([e.parse_line(line)], {e.parse_line(line)["name"]: "buy"})[0]
def solve(line, approved=False): r = req(line); return e.solve(r, asyncio.run(C.search(r["normalized_name"])), approved)

def test_range_and_trailing_sentence():
    p = e.parse_line("2-3 tbsp cake flour. All-purpose flour works too.")
    assert (p["name"], p["quantity"], p["unit"]) == ("cake flour", 24.75, "g") and "All-purpose" in p["notes"]
    assert e.parse_line("1 tbsp sugar.")["name"] == "sugar"
    assert e.parse_line("2 tomatoes")["quantity"] == 2
def test_size_word_does_not_block_match():
    r = solve("2 middle eggs"); assert r["status"] == "ok" and r["selection"][0]["product"]["name"] == "Eggs"
def test_small_amounts_now_find_products():
    for line in ["1/2 tsp vanilla extract", "1 tbsp sugar.", "20 ml milk"]:
        assert solve(line)["status"] == "ok", line
def test_related_products_offered_but_need_approval():
    r = solve("2-3 tbsp rice flour")
    assert r["status"] == "needs_substitute_approval" and 1 <= len(r["substitute_offers"]) <= 3 and not r["selection"]
    a = solve("2-3 tbsp rice flour", approved=True)
    assert a["status"] == "ok" and a["unverified"] and a["selection"][0]["packs"] == 1

def test_generic_head_nouns_do_not_offer_wrong_products():
    r = solve("2 bay leaves"); assert r["status"] == "no_match" and not r["substitute_offers"]
    assert solve("1 tsp cumin seeds")["status"] in ("no_match", "ok")
