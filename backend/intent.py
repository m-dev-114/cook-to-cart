"""Natural-language request -> dish, servings, pantry, budget. Deterministic; the text is treated as DATA, never as instructions."""
import re
import engine

BUD = re.compile(r"(?:keep (?:it|this) )?(?:under|below|within|less than|up to|budget(?: of| is)?|max(?:imum)?(?: of)?)\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*)", re.I)
PAN = re.compile(r"\b(?:i\s+)?(?:already\s+)?(?:have|got)\s+(.+?)(?:[.!?;]|$)", re.I | re.S)
SRV = re.compile(r"\bfor\s+(\d{1,2})\b(?:\s*(?:people|persons|servings|pax|members))?", re.I)


def parse_intent(s):
    s = re.sub(r"[<>]", " ", s or "")[:600]; out = {"pantry": [], "budget": None, "servings": None}
    m = BUD.search(s)
    if m: out["budget"] = float(m.group(1).replace(",", "")); s = s[:m.start()] + " " + s[m.end():]
    m = PAN.search(s)
    if m:
        for part in re.split(r",|\band\b", m.group(1)):
            p = engine.parse_line(part.strip(" .")) if part.strip(" .") else None
            if p: out["pantry"].append({"name": p["name"], "quantity": p["quantity"], "unit": p["unit"]})
        s = s[:m.start()] + " " + s[m.end():]
    m = SRV.search(s)
    if m: out["servings"] = max(1, int(m.group(1))); s = s[:m.start()] + " " + s[m.end():]
    s = re.sub(r"\b(i want to|i'd like to|i would like to|i wanna|let'?s|help me|please|keep it)\b|\b(make|cook|prepare|cooking|making)\b", " ", s, flags=re.I)
    out["dish"] = re.sub(r"\s+", " ", s).strip(" .,!?-")[:120]
    return out
