"""Deterministic core: parsing, scaling, requirements, matching, optimizer. No LLM, no arithmetic by model."""
import itertools, math, re
from fractions import Fraction

UNITS = {"g": ("g", 1), "gram": ("g", 1), "grams": ("g", 1), "kg": ("g", 1000), "ml": ("ml", 1), "l": ("ml", 1000),
         "litre": ("ml", 1000), "liter": ("ml", 1000), "tsp": ("ml", 5), "teaspoon": ("ml", 5), "tbsp": ("ml", 15),
         "tablespoon": ("ml", 15), "tbs": ("ml", 15), "quart": ("ml", 946), "quarts": ("ml", 946), "qt": ("ml", 946), "pint": ("ml", 473), "pints": ("ml", 473), "gallon": ("ml", 3785), "gallons": ("ml", 3785), "inch": ("g", 8), "inches": ("g", 8), "tbl": ("ml", 15), "cup": ("ml", 240), "cups": ("ml", 240), "gm": ("g", 1), "gms": ("g", 1), "gr": ("g", 1), "grams": ("g", 1), "kgs": ("g", 1000), "oz": ("g", 28.35), "lb": ("g", 453.6), "lbs": ("g", 453.6),
         "mls": ("ml", 1), "ltr": ("ml", 1000), "ltrs": ("ml", 1000), "lt": ("ml", 1000), "litres": ("ml", 1000), "liters": ("ml", 1000),
         "tsps": ("ml", 5), "teaspoons": ("ml", 5), "tbsps": ("ml", 15), "tablespoons": ("ml", 15), "piece": ("piece", 1),
         "pieces": ("piece", 1), "pc": ("piece", 1), "pcs": ("piece", 1), "nos": ("piece", 1), "no": ("piece", 1), "bunch": ("bunch", 1), "bunches": ("bunch", 1), "combo": ("combo", 1)}
PIECEISH = {"clove", "cloves", "slice", "slices"}
QUALS = ["bone-in", "skin-on", "boneless", "skinless", "low-fat", "full-fat", "sliced", "minced", "grated", "fresh", "frozen", "organic"]
CONFLICT = {"bone-in": ["boneless"], "skin-on": ["skinless"], "boneless": ["bone-in", "bone in", "with bone"], "skinless": ["with skin"],
            "low-fat": ["full-fat", "full fat"], "full-fat": ["low-fat", "low fat"],
            "fresh": ["frozen"], "frozen": ["fresh"]}
DENS = {"butter": 0.95, "flour": 0.55, "maida": 0.55, "sugar": 0.85, "salt": 1.2, "rice": 0.8, "milk": 1.03, "oil": 0.92, "pasta": 0.42, "pepper": 0.5, "cheese": 0.45, "corn": 0.65, "ketchup": 1.1, "capsicum": 0.6, "cardamom": 0.4, "clove": 0.4, "peppercorn": 0.55, "cumin": 0.4, "mace": 0.3, "cinnamon": 0.4, "nutmeg": 0.5, "methi": 0.15, "kasuri": 0.15, "paprika": 0.5, "chilli": 0.4, "seasoning": 0.4, "mayonnaise": 0.91, "honey": 1.4, "ghee": 0.91, "curd": 1.03, "yogurt": 1.03, "carrot": 0.54, "onion": 0.67, "tomato": 0.75, "potato": 0.6, "spinach": 0.15, "coriander": 0.2, "ginger": 0.5, "sauce": 1.1}  # approx g per ml
SUBS = {"mozzarella": ["pizza cheese"]}  # possible substitutes: ALWAYS need user approval
PREPARATION = {"chopped", "diced", "finely", "roughly", "minced", "sliced", "grated", "crushed", "cubed", "shredded", "mashed", "peeled"}
PART = {"stem", "stalk", "zest", "peel", "rind", "wedge"}  # parts of a whole item: shop for the whole item
FRAC = {"½": " 1/2", "¼": " 1/4", "¾": " 3/4", "⅓": " 1/3", "⅔": " 2/3"}
PREP = {"middle", "big", "ripe", "heaping", "level", "handful", "bunch", "sprig", "sprigs", "few", "chopped", "diced", "finely", "roughly", "medium", "large", "small", "cut", "into", "cubes", "of", "a", "the"}
VAGUE = re.compile(r"\b(to taste|as needed|as required|for (frying|serving|garnish)|a pinch|a dash)\b", re.I)
N = r"\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?"
Q = re.compile(rf"^\s*({N})(?:\s*(?:-|–|to)\s*({N}))?\s*([a-zA-Z]+)?\.?\s*(.*)$")  # supports ranges: 2-3 tbsp (uses the upper bound)


TQ = re.compile(rf"^(.+?)\s+({N})(?:\s*(?:-|–|to)\s*({N}))?\s*([a-zA-Z]+)\.?$")  # name-first lines: "ONION 1/2 KG"


def sing(w):
    if w in ("chillies", "chilies"): return "chilli"
    if w.endswith("leaves"): return w[:-3] + "f"
    if w.endswith("oes"): return w[:-2]
    if w.endswith("ies"): return w[:-3] + "y"
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3: return w[:-1]
    return w


def words(s): return re.findall(r"[a-z]+(?:-[a-z]+)*", s.lower())


def normalize_name(name): return " ".join(sing(w) for w in words(name) if w not in PREP and sing(w) not in PART)


CANON = {"gm": "g", "gms": "g", "gr": "g", "gram": "g", "grams": "g", "kgs": "kg", "mls": "ml", "ltr": "l", "ltrs": "l", "lt": "l",
         "litre": "l", "litres": "l", "liter": "l", "liters": "l", "teaspoon": "tsp", "teaspoons": "tsp", "tsps": "tsp", "tablespoon": "tbsp",
         "tablespoons": "tbsp", "tbsps": "tbsp", "tbs": "tbsp", "tbl": "tbsp", "cups": "cup", "pcs": "piece", "nos": "piece", "no": "piece", "pc": "piece", "pieces": "piece", "lbs": "lb", "quarts": "quart", "qt": "quart", "pints": "pint", "gallons": "gallon"}
LIQ = {"milk", "water", "oil", "cream", "juice", "vinegar", "stock", "broth", "extract", "wine", "syrup", "sauce", "buttermilk"}  # volume stays ml
PIECE_G = {"garlic": 4, "carrot": 70, "capsicum": 120, "onion": 110, "tomato": 100, "potato": 150, "ginger": 25, "lemon": 60,
           "cucumber": 200, "chilli": 5, "butter": 10, "brinjal": 150, "beetroot": 100, "apple": 150, "banana": 120, "egg": 55, "cashew": 1.5, "peanut": 0.8, "almond": 1.2, "jalapeno": 15, "cardamom": 2, "bay": 0.4, "mace": 0.7, "nutmeg": 7}  # est. g per piece


ALIASES = {  # canonical -> other names (Indian / British / American / regional); ordered: most store-friendly first
    "fresh coriander": ["coriander leaf", "coriander", "dhaniya", "dhania patta", "dhania", "cilantro", "kothimbir", "kothamalli", "kothimeera", "hara dhania", "dhania leaf"],
    "coriander seed": ["dhania seed", "sabut dhania", "whole coriander", "dhania whole"],
    "coriander powder": ["dhania powder"],
    "cumin seed": ["jeera", "zeera", "whole jeera", "cumin"],
    "cumin powder": ["jeera powder", "ground cumin"],
    "caraway seed": ["shahi jeera", "shah jeera", "shajeera"],
    "onion": ["pyaaz", "pyaz", "kanda", "ullipaya", "vengayam"],
    "green cardamom": ["choti elaichi", "hari elaichi", "elaichi"],
    "black cardamom": ["badi elaichi", "kali elaichi"],
    "cinnamon": ["dalchini", "cassia"],
    "clove": ["laung", "lavang"],
    "bay leaf": ["tej patta", "tejpatta", "tejpat"],
    "turmeric powder": ["haldi", "haldi powder", "turmeric"],
    "kasuri methi": ["dried fenugreek leaf", "dry fenugreek leaf", "kasoori methi"],
    "nutmeg": ["jaiphal"], "mace": ["javitri", "jawitri"],
    "black peppercorn": ["whole black pepper", "sabut kali mirch", "kali mirch"],
    "yogurt": ["curd", "dahi"],
    "ginger": ["adrak"], "garlic": ["lehsun", "lasun"],
    "green chilli": ["hari mirch", "green chili"],
    "red chilli powder": ["lal mirch powder", "chilli powder", "chili powder"],
    "mint": ["pudina", "pudhina", "mint leaf", "mint leaves", "fresh pudina", "fresh mint"],
    "dried red chilli": ["dry red chilli", "whole red chilli", "sukhi lal mirch", "chilli whole", "spicy red chilli", "red chilli whole"],
    "ghee": ["clarified butter"], "capsicum": ["bell pepper", "shimla mirch"],
    "coriander stem": ["fresh coriander"],
}
AMBIG = {"cumin", "cardamom", "dhania", "elaichi", "jeera", "pepper", "chilli"}  # one word, several products: expand the search, never auto-pick one meaning
CONTRA = {  # canonical -> words a product must NOT carry (leaves/seeds/powder, cumin/caraway, green/black cardamom ...)
    "fresh coriander": {"powder", "seed", "masala", "whole", "dry", "dried"}, "coriander seed": {"leaf", "powder", "fresh", "ground"}, "coriander powder": {"seed", "leaf", "fresh"},
    "cumin seed": {"powder", "shahi", "shah", "caraway", "black", "kala"}, "cumin powder": {"seed", "shahi", "caraway", "black"}, "caraway seed": {"powder"},
    "green cardamom": {"black", "badi", "kali", "powder"}, "black cardamom": {"green", "choti", "hari"},
    "onion": {"sambar", "sambhar", "sambhaar", "spring", "powder", "pearl", "flake", "paste", "fried"}, "bay leaf": {"powder"}, "turmeric powder": {"fresh", "root", "capsule"},
    "yogurt": {"protein", "turbo", "skyr", "drink", "shake", "smoothie", "dessert", "flavoured", "flavored", "greek", "strawberry", "mango", "blueberry", "vanilla", "lassi"}, "ginger": {"paste", "powder", "candy"}, "garlic": {"paste", "powder", "pickle"},
    "mint": {"sauce", "chutney", "tea", "candy", "chewy", "gum", "peppermint", "flavour", "flavoured", "flavor", "toffee", "chocolate", "mouth", "freshener", "sweet", "pastille", "lozenge", "mints", "doublemint", "oral", "toothpaste", "mojito", "syrup", "sugar", "free", "impact", "polo", "freshmint", "breath"}, "dried red chilli": {"powder", "sauce", "flake", "green", "fresh", "pickle", "paste"},
}
VARIETY = {"cardamom": {"black", "badi", "kali"}, "salt": {"black", "kala", "rock", "sendha", "pink", "himalayan", "lite", "low"}, "onion": {"sambar", "sambhar", "sambhaar", "pearl", "small"},
           "cumin": {"black", "shahi", "shah", "caraway"}, "pepper": {"white", "szechuan"}, "rice": {"broken", "brokens"}, "basmati": {"broken"}}  # a different kind of the same word: possible substitute, never exact
FORMW = {"powder", "ground", "paste", "flake", "crushed", "granule"}


NONFOOD = {"flavour", "flavoured", "flavor", "chewy", "sugarfree", "gum", "candy", "toothpaste", "mouthwash", "freshener", "lozenge", "chewing", "breath", "mentos", "toffee", "mouthfreshener", "pastille", "tictac"}
REQUIRE = {"mint": {"leaf", "pudina", "pudhina", "herb"}}  # fresh mint must say leaf/pudina: "Fresh Mints" is a sweet
FORMREQ = {"leaf": {"leaf", "leave", "pudina", "pudhina", "patta", "bunch", "kothimbir"}, "seed": {"seed", "whole", "jeera"}, "powder": {"powder", "ground"}, "paste": {"paste"}, "flake": {"flake"}}
LEAFW = {"leaf", "leave", "fresh", "patta", "bunch", "hara", "green"}  # words that prove "coriander/dhaniya" means the fresh herb
BARE = {"fresh coriander": {"coriander", "dhaniya", "dhania"}}  # alias forms that do NOT say leaves vs seeds vs powder


def canon(nn):
    """Canonical ingredient name: aliases/slang map to one name (cilantro -> fresh coriander). Ambiguous one-word names stay as they are."""
    if nn in ALIASES: return nn
    if nn in AMBIG: return nn
    if nn.startswith("fresh ") and nn[6:] != nn:  # fresh cilantro -> fresh coriander, fresh mint -> mint
        c = canon(nn[6:])
        if c != nn[6:]: return c
    return next((c for c, al in ALIASES.items() if nn in al and nn not in AMBIG), nn)


def search_terms(req):
    """Search queries to try, in order: canonical, aliases, bare name, head noun. Quantities and units never appear here."""
    nn = req["normalized_name"]; cn = canon(nn)
    ip = req.get("interp") or {}
    forms = [nn, cn] + ALIASES.get(cn, []) + [q for q in ip.get("queries", []) if isinstance(q, str)]  # the recipe's own words first, then the interpreted meaning
    if nn in AMBIG:  # ambiguous: try the likely meanings too
        forms += [c for c, al in ALIASES.items() if nn in al or c.endswith(" " + nn)]
        for c in list(forms): forms += ALIASES.get(c, []) if c in ALIASES and c != nn else []
    head = [w for w in nn.split() if w not in QUALS][-1:]
    if head and head[0] not in GENERIC: forms.append(head[0])
    return [f for f in dict.fromkeys(re.sub(r"\s+", " ", f).strip() for f in forms) if f][:6]


def failed_result(req, why="Instamart search failed. This is not the same as the product being unavailable; try again."):
    return {"requirement": req, "candidates": [], "selection": [], "purchased": None, "excess": None, "reasons": [why], "status": "search_failed",
            "outcome": "search_failed", "unverified": False, "unavailable": [], "substitute_offers": [], "decision": {"label": "Search failed", "evidence": [], "rejected": [], "interpretation": req.get("interp")}}


SPICEY = {"powder", "seed", "masala", "spice", "dal", "seasoning", "flake", "paste"}


def _dens(name):  # head noun wins: "tomato ketchup" -> ketchup; spices/dals get a default
    d = next((DENS[w] for w in reversed(name.split()) if w in DENS), None)
    return d or (0.5 if any(sing(t) in SPICEY for t in name.split()) else None)


def fmt(q):
    if q is None: return ""
    w, f = int(q), round(q - int(q), 2)
    fr = {0.25: "¼", 0.5: "½", 0.75: "¾", 0.33: "⅓", 0.67: "⅔"}.get(f)
    return f"{w}" if f == 0 else ((f"{w} " if w else "") + fr if fr else f"{q:g}")


def _stext(q, u):
    if q is None: return ""
    if u in ("clove", "slice", "piece", "cup") and q > 1: u += "s"
    return f"{fmt(q)} {u}".strip() if u else fmt(q)


def parse_line(line):
    """Keeps THREE quantities: source (as written), normalized cooking quantity (g/ml/piece, flagged if estimated), retail is chosen later."""
    raw = line.strip()[:200]
    if re.match(r"^\W*(serves?|servings?|yields?|makes|prep time|cook time|total time)\b", line.strip(), re.I): return None  # recipe metadata, not an ingredient
    if re.match(r"^\W*for\b", line, re.I) and not re.search(r"\d", line) or line.strip().endswith(":"): return None  # section heading
    line = re.sub(r"(\d)\s*([½¼¾⅓⅔])", r"\1 \2", line)
    for k, v in FRAC.items(): line = line.replace(k, v)
    notes = [n for n in (re.sub(r"[^\x00-\x7F]+", " ", n).strip(" -–") for n in re.findall(r"\((.*?)\)", line)) if n]  # English only: store search is English
    s = re.sub(r"[^\x00-\x7F]+", " ", re.sub(r"\(.*?\)", "", line)).strip()
    if "," in s:
        s, extra = s.split(",", 1); notes.append(extra.strip())
    opt = bool(re.search(r"\boptional\b", line, re.I))
    s = re.sub(r"\boptional\b", "", VAGUE.sub("", s), flags=re.I).strip(" -•*")
    tm = None if Q.match(s) else TQ.match(s)
    if tm and (tm[4].lower() in UNITS or tm[4].lower() in PIECEISH):  # amount-last line -> amount-first
        nm = tm[1].strip(" -–:")
        if nm.isupper(): nm = nm.title()
        s = f"{tm[2]}{('-' + tm[3]) if tm[3] else ''} {tm[4]} {nm}"
    m, name, sq, su, base, f = Q.match(s), s, None, None, None, 1
    if m:
        sq = float(sum(Fraction(p) for p in (m[2] or m[1]).split())); u = m[3] or ""; rest = m[4]
        ul = {"T": "tbsp", "t": "tsp"}.get(u) or u.lower()
        if m[2]: notes.append(f"recipe says {m[1]}-{m[2]}; upper amount used")
        if ul in UNITS: base, f = UNITS[ul]; su = CANON.get(ul, ul); name = rest
        elif ul in PIECEISH: base, su, name = "piece", ul.rstrip("s"), rest
        else: base, su, name = "piece", "piece", (u + " " + rest).strip()
    size = next((w.lower() for w in name.split() if w.lower() in ("small", "medium", "large")), None)
    prep = " ".join(dict.fromkeys(w.lower().strip(",.") for w in (name + " " + " ".join(notes)).split() if w.lower().strip(",.") in PREPARATION)) or None
    name, _, tail = name.partition(". ")  # "cake flour. All-purpose flour works too." -> name + note
    if tail.strip(): notes.append(tail.strip())
    name = " ".join(w for w in name.strip(" .-–").split() if w.lower() not in PREP and re.search(r"\w", w)).strip()
    ws = name.split()
    if su == "piece" and len(ws) > 1 and ws[-1].lower() in ("clove", "cloves"): su, name = "clove", " ".join(ws[:-1])  # "5 garlic cloves" -> garlic, 5 cloves
    if su == "piece" and ws and ws[-1].lower() in ("slice", "slices"): su = "slice"  # keep "slices" in the name: stores list "Cheese Slices"
    nn = normalize_name(name)
    if not nn: return None
    if any(sing(w) in PART for w in words(name)):  # "coriander stems" -> shop for the whole, fresh item
        notes.append("part of the whole item: buy fresh " + nn)
        if "fresh" not in nn.split(): nn = "fresh " + nn
    qty = unit = pg = None; est = False
    if sq is not None:
        qty, unit, toks = sq * f, base, nn.split()
        if base == "ml" and su in ("tsp", "tbsp", "cup") and not any(t in LIQ for t in toks):  # solids by volume -> grams (estimate)
            d = _dens(nn)
            if d: qty, unit, est = qty * d, "g", True
        if unit == "piece": pg = next((PIECE_G[t] for t in toks if t in PIECE_G), None)
        if su in ("inch", "inches"): est = True
        qty = round(qty, 2)
    return {"name": name, "quantity": qty, "unit": unit, "optional": opt, "notes": "; ".join(n for n in notes if n) or None,
            "normalized_name": nn, "source_quantity": None if sq is None else round(sq, 2), "source_unit": su,
            "source_text": _stext(None if sq is None else round(sq, 2), su), "normalized_is_estimate": est, "est_piece_g": pg, "preparation": prep, "raw_text": raw, "size": size, "canonical_name": canon(nn), "original_text": raw, "preparation_notes": prep, "search_aliases": ALIASES.get(canon(nn), [])[:6],
            "quantity_confidence": "unknown" if sq is None else ("estimated" if est else "explicit")}


def scale_ings(ings, frm, to):
    f, out = to / frm, []
    for i in ings:
        j = dict(i)
        if i.get("quantity") is not None: j["quantity"] = round(i["quantity"] * f, 2)
        if i.get("source_quantity") is not None:
            j["source_quantity"] = round(i["source_quantity"] * f, 2); j["source_text"] = _stext(j["source_quantity"], i.get("source_unit"))
        out.append(j)
    return out


_QF = ("quantity", "unit", "source_quantity", "source_unit", "source_text", "normalized_is_estimate", "est_piece_g")


def consolidate(ings):
    """Merge repeated ingredients AFTER normalization (same unit, or g/ml via density). Incompatible units stay separate."""
    out, idx = [], {}
    for g in ings:
        t = idx.get(canon(g["normalized_name"]))
        if not t: t = idx[canon(g["normalized_name"])] = dict(g); out.append(t); continue
        tq, tu, q, u, d = t.get("quantity"), t.get("unit"), g.get("quantity"), g.get("unit"), _dens(g["normalized_name"])
        if q is None: continue
        if tq is None: t.update({k: g.get(k) for k in _QF}); continue
        join = f'{t["source_text"]} + {g["source_text"]}'
        if tu == u:
            t["quantity"] = round(tq + q, 2)
            if t.get("source_unit") == g.get("source_unit") and t.get("source_quantity") is not None and g.get("source_quantity") is not None:
                t["source_quantity"] = round(t["source_quantity"] + g["source_quantity"], 2); t["source_text"] = _stext(t["source_quantity"], t["source_unit"])
            else: t["source_text"] = join
            t["normalized_is_estimate"] = bool(t.get("normalized_is_estimate") or g.get("normalized_is_estimate"))
        elif d and {tu, u} == {"g", "ml"}:
            t["quantity"] = round((tq * d if tu == "ml" else tq) + (q * d if u == "ml" else q), 2); t["unit"] = "g"
            t["source_text"], t["source_quantity"], t["normalized_is_estimate"] = join, None, True
        else: out.append(dict(g))
    return out


FREE_WATER = re.compile(r"^(?:(?:warm|hot|cold|ice|iced|boiling|lukewarm|tap|normal|room temperature)\s+)?water$")  # tap water is never shopped for


def make_requirements(ings, pantry):
    """One requirement per ingredient: repeated lines are combined (g and ml merged via approx. density where known)."""
    out = {}
    for i, g in enumerate(ings):
        if pantry.get(g["name"], "skip" if g.get("quantity") is None else "buy") != "buy": continue
        if FREE_WATER.match((g.get("normalized_name") or g["name"]).lower().strip()): continue
        nn = g.get("normalized_name") or normalize_name(g["name"]); q, u = g.get("quantity"), g.get("unit"); k = canon(nn)
        t = out.get(k)
        if t:
            tq, tu, d = t["required_quantity"], t["unit"], _dens(nn)
            merged = True
            if q is None: pass
            elif tq is None: t["required_quantity"], t["unit"] = q, u
            elif tu == u: t["required_quantity"] = round(tq + q, 2)
            elif d and {tu, u} == {"g", "ml"}:
                f = lambda x, uu: x * d if uu == "ml" else x
                t["required_quantity"], t["unit"] = round(f(tq, tu) + f(q, u), 2), "g"
            else: merged = False
            if merged:
                t["_n"] += 1; t["source_text"] = None; t["notes"] = f"combined from {t['_n']} recipe lines"; continue
            k = f"{canon(nn)}#{i}"
        out[k] = {"requirement_id": f"r{i}", "ingredient_name": g["name"], "normalized_name": nn, "required_quantity": q,
                  "unit": u, "category": None, "optional": g.get("optional", False), "notes": g.get("notes"), "_n": 1,
                  "source_text": g.get("source_text"), "est_piece_g": g.get("est_piece_g"), "normalized_is_estimate": bool(g.get("normalized_is_estimate"))}
    return [{k: v for k, v in r.items() if k != "_n"} for r in out.values()]


def pack_base(p):
    q, u = p.get("pack_quantity"), (p.get("pack_unit") or "").lower()
    if not q or u not in UNITS: return None
    b, f = UNITS[u]; return (b, q * f)


# Equivalent / close names. kind "alias" = the same thing sold under another name (no approval needed);
# kind "close" = related product the user must pick explicitly. (pattern on normalized name, product phrases, kind, demote words, exclude words)
EQUIV = [
    (r"\b(all.?purpose|plain|white|bread|cake) flour\b", ["maida", "refined flour", "wheat flour", "all purpose flour"], "alias", [], []),
    (r"\b(cooking|vegetable|frying|neutral|high temperature) oil\b", ["oil"], "alias", ["olive", "virgin", "sesame", "coconut"], []),
    (r"\b(lime|lemon)\b", ["lemon", "lime"], "close", [], ["juice", "squash", "pickle"]),
    (r"\b(green|spring) onion\b|\bscallion\b", ["spring onion", "green onion", "scallion"], "alias", [], []),
    (r"\bbuttermilk\b", ["buttermilk", "chaas", "curd", "yogurt", "dahi"], "close", [], []),
    (r"\bhot sauce\b", ["hot sauce", "chilli sauce", "chili sauce", "sriracha", "tabasco", "peri peri"], "alias", [], []),
    (r"\bvinegar\b", ["vinegar"], "alias", [], []),
    (r"\bsoy sauce\b", ["soy sauce"], "alias", [], []),
    (r"\bchicken\b", ["chicken"], "close", [], ["liver", "sausage", "seasoning", "stock", "masala", "nugget", "spice", "cube", "kebab", "kabab", "reshmi", "tikka", "popcorn", "patty", "salami", "ham", "momo", "samosa", "tandoori", "cutlet", "burger", "seekh", "lollipop", "cooked", "fried", "ready", "marinated", "roll", "sandwich", "pickle", "biryani", "paste", "soup", "pizza", "keema"]),
    (r"\bpotato starch\b", ["potato starch", "corn starch", "cornflour", "corn flour", "tapioca"], "close", [], []),
    (r"\bcayenne\b", ["cayenne", "red chilli powder", "chilli powder", "chili powder"], "alias", [], []),
    (r"\bgochujang\b", ["gochujang", "chilli paste", "chili paste"], "close", [], []),
    (r"\bmsg\b", ["monosodium glutamate", "msg"], "alias", [], []),
    (r"\b(kosher|sea|table) salt\b", ["salt"], "alias", [], []),
    (r"\bwhite pepper\b", ["pepper"], "close", [], []),
    (r"\bjalapeno\b", ["jalapeno", "green chilli"], "close", [], []),
    (r"\bgreen cabbage\b", ["cabbage"], "alias", [], []),
    (r"\bbaking soda\b", ["baking soda", "sodium bicarbonate", "cooking soda"], "alias", [], []),
]
IDENT = {"flavoured", "flavored", "blueberry", "strawberry", "mango", "vanilla", "chocolate", "spring", "sauce", "paste", "juice", "pickle", "ketchup", "extract", "cube", "soup", "chip", "oil", "vinegar", "starch", "mix", "masala", "alternative", "substitute", "imitation", "vegan", "plant", "analogue", "faux", "premix", "instant", "seasoning"}
VEGS = {"garlic", "onion", "ginger", "tomato", "carrot", "potato", "capsicum", "coriander", "cabbage", "lemon", "lime", "cucumber", "spinach"}


def _equiv(nn):
    return next(((ph, k, av, ex) for pat, ph, k, av, ex in EQUIV if re.search(pat, nn)), None)


def score(req, p):
    nn = req["normalized_name"]; toks = nn.split()
    quals = [w for w in toks if w in QUALS]; core = [w for w in toks if w not in QUALS]
    text = f'{p["name"]} {p.get("variant") or ""}'.lower()
    ptoks = {sing(w) for w in words(text)}
    eq = _equiv(nn); exact = all(sing(c) in ptoks for c in core)
    cn = canon(nn); contra = CONTRA.get(cn, set())
    if NONFOOD & ptoks - set(toks) or (re.search(r"sugar.?free", text) and "sugar" not in toks): return 0.0, ["Not a food ingredient (confectionery / flavoured / personal-care product)"], False  # chewing gum, mints, toothpaste ... are never an ingredient
    if contra and (contra & ptoks) - set(toks) - {sing(t) for t in cn.split()}: return 0.0, ["Different form or variety than the recipe asks for"], False  # leaves/seeds/powder, green/black cardamom, plain/flavoured yogurt: never confused
    ah = None
    ip = req.get("interp") or {}; llm_al = [a for a in ip.get("aliases", []) if isinstance(a, str)]
    if not exact and (cn in ALIASES or llm_al):  # same ingredient, other name (cilantro = coriander leaves): alias-equivalent, not "exact"
        ah = next((f for f in [cn] + ALIASES.get(cn, []) if f not in AMBIG and all(sing(w) in ptoks for w in words(f))), None)
        from_llm = False
        if not ah: ah = next((f for f in llm_al if all(sing(w) in ptoks for w in words(f))), None); from_llm = bool(ah)  # a model-suggested name: only accepted after the live product confirms it
        fx = ((IDENT | FORMW | {"powder", "seed", "dried"}) & ptoks) - {sing(t) for t in toks} - {sing(w) for w in words(ah or "")}
        if ah and fx: return 0.4, ["Different form: " + ", ".join(sorted(fx))], True
        if ah and from_llm: return (0.8 if (ip.get("confidence") or 0) >= 0.8 else 0.5), [f"Also sold as '{ah}' (model-suggested name, confidence {ip.get('confidence')}; confirmed on the live product)"], (ip.get("confidence") or 0) < 0.8
        fw = next((f for f in FORMREQ if f in {sing(t) for t in toks}), None)  # request names a form (leaf/seed/powder...): the product must show it
        if ah and fw and not (FORMREQ[fw] & ptoks) and p.get("pack_unit") != "bunch": return 0.5, [f"Product name doesn't confirm the form ('{fw}'): please check"], True
        if ah and ah in BARE.get(cn, ()) and not (LEAFW & ptoks):  # "Coriander (Dhaniya)" 100 g: seeds, powder or leaves? unverified -> needs review
            return 0.5, [f"Product name doesn't say whether this is fresh leaves, seeds or powder ('{ah}')"], True
        if ah: return 0.9, [f"Also sold as '{ah}'"], False
    if eq and any(x in ptoks and x not in toks for x in eq[3]): return 0.0, ["Different product type (e.g. offal, sausage, stock)"], False  # chicken != chicken liver / sausage / stock, even on a name match
    sc, sub, why = 1.0, False, []
    if exact:
        why.append("Matches requirement")
        extra = (IDENT | (SPICEY if set(core) & VEGS else set())) & ptoks - {sing(c) for c in core}
        if extra and set(core) & VEGS: return 0.0, ["Processed form of a fresh ingredient (paste/powder/etc.)"], False  # ginger != ginger paste, garlic != garlic powder, onion != spring onion: INELIGIBLE  # "onion" must not pick "spring onion"/"garlic powder"
        paren = {sing(w) for g in re.findall(r"\((.*?)\)", p["name"]) for w in words(g)}
        named = bool(core) and all(sing(c) in paren for c in core)  # the product itself states "X (Amchur)": its own bracketed name confirms the identity
        if extra and named: extra = set(); why.append("Product's own bracketed name confirms it")
        if extra: sc, sub = sc * 0.4, True; why.append("Different form: " + ", ".join(sorted(extra)))  # never an exact match: needs the user's OK
        vset = next((v for k, v in VARIETY.items() if k in {sing(c) for c in core}), set())
        var = (vset & ptoks - set(toks)) if not (vset & set(toks)) else set()  # the request names a variety itself (black salt): its synonyms (kala) are not a mismatch
        if var: return (sc * 0.4, ["Different variety: " + ", ".join(sorted(var))], True)  # black salt != salt, sambar onion != onion
        mixed = (VEGS & ptoks) - {sing(c) for c in core} - {sing(t) for t in toks}
        if mixed and (set(core) & VEGS): return (sc * 0.4, ["Combined product (also contains " + ", ".join(sorted(mixed)) + "), not the plain ingredient"], True)  # ginger paste != ginger-garlic paste
        fm = (FORMW & ptoks) - set(toks) - {sing(c) for c in core}
        okf = {w for f in [cn] + ALIASES.get(cn, []) for w in words(f)}  # a form the ingredient is normally sold in (turmeric -> powder) is fine
        fm = fm - okf
        if fm and not extra and not named and not (set(core) & VEGS) and (len(core) > 1 or cn in ALIASES): sc, sub = sc * 0.4, True; why.append("Different form: " + ", ".join(sorted(fm)))  # cinnamon != cinnamon powder
    elif any(s in text for s in SUBS.get(" ".join(core), [])):
        sc, sub = 0.5, True; why.append("Possible substitute (not the requested ingredient)")
    else:
        if not eq or any(x in text for x in eq[3]): return 0.0, ["Name does not identify the ingredient"], False
        hit = next((h for h in eq[0] if all(sing(w) in ptoks for w in words(h))), None)
        if not hit: return 0.0, ["Name does not identify the ingredient"], False
        if eq[1] == "alias": sc = 0.95; why.append(f"Also sold as '{hit}'")
        else: sc, sub = 0.5, True; why.append(f"Close match ('{hit}')")
        if any(a in text for a in eq[2]): sc *= 0.8
    for q in quals:
        if any(c in text for c in CONFLICT.get(q, [])):
            if not eq: return 0.0, ["Conflicts with a required attribute"], False
            sc, sub = min(sc * 0.7, 0.5), True; why.append(f"'{q}' differs from the recipe"); continue
        if q == "fresh" and q not in text and (p.get("pack_unit") or "").lower() in ("g", "ml") and 0 < (p.get("pack_quantity") or 0) < 30:
            sc, sub = min(sc * 0.5, 0.5), True; why.append("Tiny pack, not stated fresh: may not be fresh produce"); continue  # a 13 g tin of mints is not a fresh herb
        if q in text: why.append(f"'{q}' confirmed")
        else: sc *= 0.85; why.append(f"'{q}' not stated on product")
    return sc, why, sub


def candidates(req, products, strict=True):
    out = []
    for p in products:
        if not p.get("availability") or p.get("price") is None: continue
        sc, why, sub = score(req, p)
        pb = pack_base(p)
        if sc <= 0 or pb is None: continue
        if strict and req["required_quantity"] is not None and pb[0] != req["unit"]:
            d = _dens(req["normalized_name"])  # compare ml with g per product when a density is known
            if d and (req["unit"], pb[0]) == ("ml", "g"): pb = ("ml", pb[1] / d)
            elif d and (req["unit"], pb[0]) == ("g", "ml"): pb = ("g", pb[1] * d)
            else: continue
            why = why + ["Pack size compared using approx. density"]
        if pb[0] == "combo" and not sub: sub, sc, why = True, sc * 0.5, why + ["Combo pack: contains more than the requested item"]
        out.append({"product": p, "score": round(sc, 3), "substitute": sub, "reasons": why, "pack": pb})
    return sorted(out, key=lambda c: (-c["score"], c["product"]["price"]))


def _convert(req, products):
    """Compare in the unit the store sells: ml->g (density) or piece->g (est. weight per piece). Source text is kept as 'original'."""
    q, u, nn = req["required_quantity"], req["unit"], req["normalized_name"]
    if q is None: return req
    has = lambda unit: any((pack_base(p) or ("", 0))[0] == unit and score(req, p)[0] > 0 for p in products)
    if u == "ml" and _dens(nn) and not has("ml"): g = q * _dens(nn); note = f"{q:g} ml converted to g (approx. density)"
    elif u == "piece" and req.get("est_piece_g") and not has("piece") and has("g"): g = q * req["est_piece_g"]; note = f"{q:g} piece(s) converted to g (estimated weight)"
    else: return req
    return {**req, "original": req.get("source_text") or f"{q:g} {u}", "required_quantity": round(g, 1), "unit": "g", "estimated": True,
            "notes": note + (f"; {req['notes']}" if req.get("notes") else "")}


GENERIC = {"leaf", "leave", "powder", "seed", "flake", "paste", "sauce", "mix", "extract", "spice", "stick", "piece"}


def related(req, products):
    """Last resort: products sharing the ingredient's head noun (e.g. 'cake flour' -> flours). Always needs user approval."""
    core = [w for w in req["normalized_name"].split() if w not in QUALS]
    head = core[-1] if core else ""
    if len(head) < 3 or head in GENERIC: return []  # "bay leaf" must not offer basil
    out = []
    for p in products:
        if not p.get("availability") or p.get("price") is None: continue
        text = f'{p["name"]} {p.get("variant") or ""}'.lower(); pb = pack_base(p)
        pt = {sing(w) for w in words(text)}
        eqx = _equiv(req["normalized_name"])
        if eqx and any(x in text for x in eqx[3]): continue  # e.g. chicken liver is never a "related" chicken product
        if pb is None or sing(head) not in pt: continue
        cn_ = canon(req["normalized_name"]); toks_ = set(req["normalized_name"].split())
        if NONFOOD & pt - toks_: continue  # gum/candy/toothpaste is never "related" to an ingredient
        if set(core) & VEGS and (IDENT | SPICEY | {"spring"}) & pt - {sing(c) for c in core}: continue  # a different form of a vegetable is never a "related" product
        if any(c in text for q in req["normalized_name"].split() for c in CONFLICT.get(q, [])): continue
        out.append({"product": p, "score": 0.4, "substitute": True, "pack": pb,
                    "reasons": [f"Related product (name differs from '{req['ingredient_name']}')"]})
    return sorted(out, key=lambda c: c["product"]["price"])


def top_live(req, products, k=1):
    """Last resort when no name evidence exists (regional/unfamiliar names): Instamart's own top result for the ORIGINAL term, offered for review only.
    The search engine's ranking is evidence of relevance, never proof: hard rejections still apply and the user must approve."""
    toks = set(req["normalized_name"].split()); wanted = {f for f in FORMREQ if f in {sing(t) for t in toks}}; out = []
    for p in products:
        r = p.get("_rank")
        if r is None or r >= k or not p.get("availability") or p.get("price") is None: continue
        pb = pack_base(p) or (("pack", 1) if (p.get("pack_unit") or "") in ("bunch", "combo") else None)
        if pb is None: continue
        text = f'{p["name"]} {p.get("variant") or ""}'.lower(); pt = {sing(w) for w in words(text)}
        if NONFOOD & pt - toks or re.search(r"sugar.?free", text): continue
        if {w for g, ws in FORMREQ.items() if g not in wanted and g in ("powder", "paste", "flake", "seed") for w in ws} & pt - toks: continue  # a different form than the recipe asks for
        if (IDENT & pt) - toks: continue
        out.append({"product": p, "score": 0.35, "substitute": True, "pack": pb, "reasons": [f"Instamart's top result for '{req['ingredient_name']}' (the name doesn't confirm it): please check"]})
    return out


def unavailable(req, products):
    out = []
    for p in products:
        if p.get("availability") or pack_base(p) is None: continue
        sc, why, sub = score(req, p)
        if sc > 0: out.append({"product": p, "score": round(sc, 3), "substitute": sub, "reasons": why})
    return out[:6]


def _match(c):  # INELIGIBLE products never reach this point (score 0 = not offered)
    return "POSSIBLE_ALTERNATIVE" if c["substitute"] else ("VALID_VARIANT" if c["reasons"] and c["reasons"][0].startswith("Also sold as") else "EXACT_MATCH")


def _pub(c, approved=False): return {**{k: c[k] for k in ("product", "score", "substitute", "reasons")}, "match": "USER_ACCEPTED_SUBSTITUTION" if approved and c["substitute"] else _match(c)}


def _best(pool, need, mode="best"):
    top = pool[0]["score"]
    tier = [c for c in pool if c["score"] >= top - (0.04 if mode == "best" else 0.15)][:4]  # "best fit" prefers an exact match over a cheaper alias/variant
    if need is None: return [(min(tier, key=lambda c: c["product"]["price"]), 1)]
    best = None
    for counts in itertools.product(range(9), repeat=len(tier)):
        tot = sum(n * c["pack"][1] for n, c in zip(counts, tier))
        if tot < need - 1e-9: continue
        cost = sum(n * c["product"]["price"] for n, c in zip(counts, tier))
        pen = 2 * sum(n * c["product"]["price"] * (1 - c["score"]) for n, c in zip(counts, tier))
        obj = cost + pen + 5 * (sum(1 for n in counts if n) - 1) + 3 * sum(counts) + (0.25 * cost * (tot - need) / tot if tot else 0) + 1e-3 * tot - 0.5 * sum((c['product'].get('rating') or 0) for n, c in zip(counts, tier) if n)  # tie-break: smaller pack when otherwise comparable
        if mode == "cheapest": obj = cost + 1e-3 * tot
        elif mode == "least_excess": obj = (tot - need) * 1000 + cost
        if best is None or obj < best[0]: best = (obj, counts)
    if best is None:
        c = min(tier, key=lambda c: c["product"]["price"] / c["pack"][1])
        return [(c, math.ceil(need / c["pack"][1] - 1e-9))]
    return [(c, n) for n, c in zip(best[1], tier) if n]


def _round_est(x):
    """No false precision on estimates: 2 significant figures above 10, one decimal below."""
    if x is None: return None
    if x >= 10:
        mag = 10 ** (len(str(int(x))) - 2); return float(int(round(x / mag)) * mag)
    return round(x, 1)


def _native(req0, req, combo):
    """Purchased/leftover in the unit the PRODUCT is sold in. The recipe need is converted into that unit (never the reverse),
    and anything that used a density / piece weight is flagged estimated. None = no reliable conversion."""
    pbs = [pack_base(c["product"]) for c, _ in combo]
    if not pbs or any(b is None for b in pbs) or len({b[0] for b in pbs}) != 1: return None
    pu, tot = pbs[0][0], sum(n * b[1] for (_, n), b in zip(combo, pbs))
    q0, u0 = req0["required_quantity"], req0["unit"]
    est = bool(req0.get("normalized_is_estimate") or req.get("estimated"))
    if q0 is None: return {"unit": pu, "purchased": tot, "excess": None, "estimated": False, "need": None, "covers": True}
    d = _dens(req0["normalized_name"])
    if u0 == pu: need = q0
    elif d and (u0, pu) == ("ml", "g"): need, est = q0 * d, True
    elif d and (u0, pu) == ("g", "ml"): need, est = q0 / d, True
    elif u0 == "piece" and pu == "g" and req0.get("est_piece_g"): need, est = q0 * req0["est_piece_g"], True
    else: return None
    ex = max(tot - need, 0)
    return {"unit": pu, "purchased": tot, "excess": _round_est(ex) if est else round(ex, 2), "estimated": est, "need": need, "covers": tot >= need - 1e-9}


def _solve_core(req, products, approved=False, override=None, packs=None, mode="best"):
    req0 = req
    req = _convert(req, products)
    cands = candidates(req, products); unv = False
    if not cands:  # name matches but units can't be compared (e.g. "10 cloves" vs a 100 g pack): show packs, default to 1
        cands = candidates(req, products, strict=False); unv = bool(cands)
    if not cands:  # nothing matches by name: offer related products (user must approve), 1 pack by default
        cands = related(req, products) or top_live(req, products); unv = bool(cands)
    need = None if unv else req["required_quantity"]
    res = {"requirement": req, "candidates": [_pub(c, approved) for c in cands], "selection": [], "purchased": None, "excess": None,
           "reasons": [], "status": "no_match", "outcome": "no_suitable_product", "unverified": unv, "unavailable": unavailable(req, products),
           "substitute_offers": [_pub(c) for c in cands if c["substitute"] and not approved][:3]}
    pool = [c for c in cands if approved or not c["substitute"]]
    if override:
        c = next((c for c in cands if c["product"]["product_id"] == override), None)
        if not c: raise ValueError("Unknown product for override")
        if c["substitute"] and not approved: raise ValueError("Substitute requires approval")
        combo = [(c, 1 if need is None else math.ceil(need / c["pack"][1] - 1e-9))]; why = "Chosen by you"
    elif pool: combo = _best(pool, need, mode); why = "Best-value valid option among the live results fetched"
    else:
        res["status"] = "needs_substitute_approval" if res["substitute_offers"] else "no_match"; res["outcome"] = "possible_substitute" if res["substitute_offers"] else "no_suitable_product"; return res
    if packs and len(combo) == 1: combo = [(combo[0][0], packs)]; why += "; pack count set by you"
    tot = sum(n * c["pack"][1] for c, n in combo)
    ex = None if need is None else round(max(tot - need, 0), 2)
    res["selection"] = [{"product": c["product"], "packs": n, "line_total": round(n * c["product"]["price"], 2)} for c, n in combo]
    res["outcome"] = "substitute_approved" if combo[0][0]["substitute"] else ("alias_equivalent" if _match(combo[0][0]) == "VALID_VARIANT" else "exact")
    res["estimated"] = bool(req.get("estimated") or req.get("normalized_is_estimate"))
    res.update(status="ok", purchased=None if need is None else round(tot, 2), excess=ex, purchased_unit=req["unit"], covers=need is None or tot >= need - 1e-9)
    nat = None if unv else _native(req0, req, combo)
    if nat:
        res.update(purchased=None if nat["need"] is None else round(nat["purchased"], 2), purchased_unit=nat["unit"], excess=nat["excess"], estimated=nat["estimated"], covers=nat["covers"])
        if nat["estimated"]: res["quantity_state"] = "estimated"
        ex, tot, need, req = nat["excess"], nat["purchased"], nat["need"], {**req, "unit": nat["unit"]}
    res["quantity_state"] = "unverified" if unv else ("none" if need is None else res.get("quantity_state") or ("estimated" if res["estimated"] else "verified"))
    sel0 = combo[0][0]; res["selected_match"] = "USER_ACCEPTED_SUBSTITUTION" if approved and sel0["substitute"] else _match(sel0)
    rs = ["Matches requirement" if not combo[0][0]["substitute"] else "Substitute approved by you", "Available"]
    if unv: rs.append(f"⚠ Can't compare the recipe amount ({req.get('original') or req.get('source_text') or format(req['required_quantity'], 'g') + ' ' + str(req['unit'])}) with pack sizes: defaulting to 1 pack, adjust packs if needed")
    elif need is None: rs.append("No quantity in recipe: 1 pack of cheapest option")
    elif tot < need - 1e-9: rs.append(f"⚠ Covers only {round(tot, 2)} of {need:g} {req['unit']}")
    else: rs.append("Exact required quantity" if ex == 0 else f"Covers requirement, {'about ' if res['estimated'] else ''}{ex:g} {req['unit']} left over{' (estimated conversion)' if res['estimated'] else ''}")
    res["reasons"] = rs + [why]
    return res


LABEL = {"EXACT_MATCH": "Exact match", "VALID_VARIANT": "Suitable alternative", "POSSIBLE_ALTERNATIVE": "Needs review", "USER_ACCEPTED_SUBSTITUTION": "Approved by you"}


def solve(req, products, approved=False, override=None, packs=None, mode="best"):
    """Stage C-E: validate every live product against the ingredient, rank, decide. The result carries the evidence (why accepted / why rejected)."""
    res = _solve_core(req, products, approved, override, packs, mode)
    st = res["status"]
    if st == "ok": lab = LABEL.get(res.get("selected_match"), "Needs review")
    elif st == "needs_substitute_approval": lab = "Needs review"
    elif st == "search_failed": lab = "Search failed"
    else: lab = "Unavailable"
    r = res["requirement"]; vocab = {sing(w) for f in [canon(r["normalized_name"]), r["normalized_name"]] + ALIASES.get(canon(r["normalized_name"]), []) + list((r.get("interp") or {}).get("aliases", [])) for w in words(f)}
    rej = []
    for p in products:
        if len(rej) >= 8: break
        sc, why, _ = score(r, p)
        if sc == 0 and why and {sing(w) for w in words(p["name"])} & vocab: rej.append({"name": p["name"], "reason": why[0]})
    res["decision"] = {"label": lab, "evidence": (res.get("reasons") or [])[:4] if st == "ok" else [], "rejected": rej, "interpretation": r.get("interp")}
    return res


def merge_cart(cart, items):
    by = {i["product_id"]: dict(i) for i in cart}
    for it in items:
        if it["product_id"] in by: by[it["product_id"]]["packs"] += it["packs"]
        else: by[it["product_id"]] = dict(it)
    return list(by.values())


def apply_pantry(reqs, items):
    """Subtract pantry quantities. Unknown/uncomparable amounts are NEVER assumed to be enough: status 'unknown' (not bought, but not counted as proven)."""
    byn = {normalize_name(p["name"]): p for p in items}
    out, have = [], []
    for r in reqs:
        p = byn.get(r["normalized_name"])
        if not p: out.append(r); continue
        hq, hu, rq, ru, d = p.get("quantity"), p.get("unit"), r["required_quantity"], r["unit"], _dens(r["normalized_name"])
        if hq is not None and hu and rq is not None:
            if hu != ru and d and {hu, ru} == {"g", "ml"}: hq, hu = (hq * d if ru == "g" else hq / d), ru
            if hu == ru:
                left = round(rq - hq, 2)
                if left <= 0: have.append({"name": r["ingredient_name"], "status": "full"})
                else: out.append({**r, "required_quantity": left, "pantry_have": f"{hq:g} {hu}"})
                continue
        have.append({"name": r["ingredient_name"], "status": "unknown"})
    return out, have


def coverage(items, have, skipped):
    """Recipe coverage from real requirements: pantry sufficient, valid product selected, or user-approved substitute. Searched != covered."""
    rows = [{"name": h["name"], "state": "have" if h.get("status") == "full" else "have_unknown"} for h in have] + [{"name": n, "state": "skipped"} for n in skipped]
    for it in items:
        r, st = it["requirement"], it["status"]
        if r.get("optional"): continue
        if st == "search_failed": state = "search_failed"
        elif st == "no_match": state = "unavailable" if it.get("unavailable") else "missing"
        elif st == "needs_substitute_approval": state = "substitution_pending"
        elif it.get("unverified"): state = "assumed"
        elif not it["covers"] if "covers" in it else (r["required_quantity"] is not None and (it["purchased"] or 0) < r["required_quantity"] - 1e-9): state = "partial"
        else:
            sel = it["selection"][0]["product"]["product_id"]
            state = "substituted" if any(c["substitute"] and c["product"]["product_id"] == sel for c in it["candidates"]) else "covered"
        rows.append({"name": r["ingredient_name"], "state": state, "estimated": bool(it.get("estimated")), "match": it.get("selected_match") if state in ("covered", "substituted", "partial", "assumed") else None, "qstate": it.get("quantity_state")})
    cnt = lambda *ss: sum(r["state"] in ss for r in rows)
    counts = {"to_buy": sum(1 for it in items if not it["requirement"].get("optional")), "selected": cnt("covered", "substituted", "partial", "assumed"), "pantry": cnt("have", "have_unknown"), "verified": sum(r["state"] in ("covered", "substituted") and not r.get("estimated") for r in rows), "estimated": sum(r["state"] in ("covered", "substituted") and bool(r.get("estimated")) for r in rows), "unverified": cnt("assumed"),
              "exact": sum(r.get("match") == "EXACT_MATCH" for r in rows), "alternative": sum(r.get("match") == "VALID_VARIANT" for r in rows),
              "approved": sum(r.get("match") == "USER_ACCEPTED_SUBSTITUTION" for r in rows), "needs_review": cnt("substitution_pending", "partial"),
              "unavailable": cnt("missing", "unavailable", "search_failed"), "qty_verified": sum(r.get("qstate") == "verified" for r in rows),
              "qty_estimated": sum(r.get("qstate") == "estimated" for r in rows), "qty_unverified": sum(r.get("qstate") in ("unverified", "none") for r in rows),
              "skipped": cnt("skipped"), "unresolved": cnt("missing", "unavailable", "substitution_pending", "search_failed")}
    return {"counts": counts, "total": len(rows), "covered": sum(r["state"] in ("have", "covered", "substituted") for r in rows),
            "assumed": sum(r["state"] in ("have_unknown", "assumed") for r in rows), "rows": rows}


def plan_cart(before, new):
    """Desired live cart = existing items + recipe items at AT LEAST the recipe quantity. Already-satisfied items are not duplicated, so a retry is idempotent."""
    cur = {i["product_id"]: i["packs"] for i in before}; desired = [dict(i) for i in before]; changes = []
    for it in new:
        have = cur.get(it["product_id"], 0)
        if have >= it["packs"]: continue
        changes.append({"product_id": it["product_id"], "from": have, "to": it["packs"]})
        hit = next((d for d in desired if d["product_id"] == it["product_id"]), None)
        if hit: hit["packs"] = it["packs"]
        else: desired.append(dict(it))
    return desired, changes


def reconcile(before, desired, after):
    """Compare the LIVE cart with the desired state: CONFIRMED / NOT_APPLIED / PARTIAL. (UNKNOWN is when the live cart can't be read.)"""
    a, d, b = ({i["product_id"]: i["packs"] for i in x} for x in (after, desired, before))
    if all(a.get(k, 0) >= v for k, v in d.items()): return "CONFIRMED"
    return "NOT_APPLIED" if a == b else "PARTIAL"


ESSENTIALS = [  # (dish pattern, [(label, ingredient words that satisfy it)])
    (r"\bbiryani\b|\bpulao\b|\bpulav\b", [("rice", {"rice", "basmati"})]),
    (r"\bchicken\b", [("chicken", {"chicken"})]),
    (r"\b(mutton|lamb|goat)\b", [("mutton", {"mutton", "lamb", "goat"})]),
    (r"\bpaneer\b", [("paneer", {"paneer"})]),
    (r"\bfish\b", [("fish", {"fish"})]),
    (r"\b(pasta|spaghetti|penne|macaroni)\b", [("pasta", {"pasta", "spaghetti", "penne", "macaroni"})]),
    (r"\bdal\b|\blentil\b", [("dal", {"dal", "lentil", "toor", "moong", "masoor", "chana", "urad"})]),
]


def missing_essentials(title, ings):
    """Core ingredients the dish name implies but the extracted list lacks. Only SUGGESTED: the user confirms; nothing is added silently."""
    title = re.sub(r"\s+", " ", re.sub(r"[^\x00-\x7F]+", " ", (title or "").split("|")[0])).strip()  # English part only, e.g. "Chicken Dum Biryani Recipe"
    have = {sing(w) for i in ings for w in words(i.get("normalized_name") or i.get("name") or "")}
    out = []
    for pat, need in ESSENTIALS:
        if not re.search(pat, (title or "").lower()): continue
        for label, ws in need:
            if not (have & {sing(w) for w in ws}) and label not in [o["name"] for o in out]:
                out.append({"name": label, "reason": f"The dish looks like '{title[:60]}', but no {label} was found in the extracted ingredients."})
    return out
