"""Stage B: live product retrieval shared by recipe matching and the manual 'Add additional items' search.
Every product returned here comes from the Instamart MCP client; nothing is invented. Identical queries within a short window reuse the same live results."""
import time
import engine, swiggy

TTL, MAXC = 90, 400
_CACHE = {}


async def search_cached(client, q, addr, sid):
    key = (id(client), sid, addr, q.strip().lower()[:100])
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < TTL: return [dict(p) for p in hit[1]]
    ps = await client.search(q[:100], addr, sid)
    if len(_CACHE) > MAXC: _CACHE.clear()
    _CACHE[key] = (time.monotonic(), [dict(p) for p in ps])
    return [dict(p) for p in ps]


async def retrieve(client, rd, addr, sid, max_queries=4):
    """Search the recipe's own words first, then the interpreted meaning (aliases / model-suggested names), merging by product id.
    Returns (products, error|None); error only when EVERY query failed (that is a search failure, not 'unavailable').
    Products from the first query carry `_rank` (Instamart's own relevance order) which the matcher may use as weak evidence."""
    seen, merged, errs, ok, last = set(), [], 0, 0, None
    for qi, q in enumerate(engine.search_terms(rd)[:max_queries]):
        try: ps = await search_cached(client, q, addr, sid)
        except swiggy.NeedLogin: raise
        except swiggy.SwiggyError as e: errs += 1; last = e; continue
        ok += 1
        for rank, p in enumerate(ps):
            if p["product_id"] not in seen:
                seen.add(p["product_id"])
                if qi == 0: p["_rank"] = rank
                merged.append(p)
        if any(c["score"] >= 0.85 and not c["substitute"] for c in engine.candidates(rd, merged, strict=False)): break  # a proper match exists: stop searching
    return merged, (last if ok == 0 and errs else None)


async def manual_search(client, q, addr, sid):
    """Broad, user-driven search: same live data and de-duplication, no ingredient suitability filter (the user chooses)."""
    return await search_cached(client, q, addr, sid)
