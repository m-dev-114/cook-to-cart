import asyncio, ipaddress, json, re, socket
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup
import llm
import visual

MAX_BYTES = 2_000_000


class ExtractError(Exception): pass


def _resolve(host):
    try: infos = socket.getaddrinfo(host, None)
    except socket.gaierror: raise ExtractError("Could not resolve that host.")
    for i in infos:
        if not ipaddress.ip_address(i[4][0]).is_global: raise ExtractError("URL points to a non-public address.")
    return infos[0][4][0]


async def fetch(url):
    for _ in range(4):  # manual redirects, each hop re-validated; connect to the validated IP (anti DNS-rebinding)
        u = urlparse(url)
        if u.scheme not in ("http", "https") or not u.hostname or u.username or u.port not in (None, 80, 443) or len(url) > 2048:
            raise ExtractError("Only public http(s) URLs are supported.")
        ip = await asyncio.to_thread(_resolve, u.hostname)
        host = f"[{ip}]" if ":" in ip else ip
        target = f"{u.scheme}://{host}{u.path or '/'}" + (f"?{u.query}" if u.query else "")
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, headers={"User-Agent": "RecipeToCartBot/1.0"}) as c:
            async with c.stream("GET", target, headers={"Host": u.netloc}, extensions={"sni_hostname": u.hostname}) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, r.headers.get("location", "")); continue
                if r.status_code != 200: raise ExtractError(f"The site returned HTTP {r.status_code}.")
                buf = b""
                async for ch in r.aiter_bytes():
                    buf += ch
                    if len(buf) > MAX_BYTES: raise ExtractError("Page is too large.")
                return buf.decode(r.encoding or "utf-8", "ignore")
    raise ExtractError("Too many redirects.")


def _nodes(d):
    if isinstance(d, list):
        for x in d: yield from _nodes(x)
    elif isinstance(d, dict):
        yield d
        if "@graph" in d: yield from _nodes(d["@graph"])


def _yield(v):
    m = re.search(r"\d+", str(v[0] if isinstance(v, list) and v else v or ""))
    return int(m.group()) if m else 4


def parse_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for s in soup.find_all("script", type="application/ld+json"):
        try: data = json.loads(s.string or "")
        except ValueError: continue
        for n in _nodes(data):
            t = n.get("@type"); t = t if isinstance(t, list) else [t]
            if "Recipe" in t and n.get("recipeIngredient"):
                return {"title": str(n.get("name", "Recipe"))[:150], "servings": _yield(n.get("recipeYield")),
                        "lines": [str(i) for i in n["recipeIngredient"]][:80], "source": "schema.org JSON-LD"}
    lis = [li.get_text(" ", strip=True) for li in soup.select('[class*="ingredient"] li, li[class*="ingredient"]')]
    if lis:
        return {"title": (soup.title.string or "Recipe").strip()[:150] if soup.title else "Recipe", "servings": 4,
                "lines": lis[:80], "source": "HTML DOM"}
    return None


HEAD = re.compile(r"^\W*(ingredients?|what you(?:'|’)?(?:ll| will)? ?need|you(?:'|’)?ll need|you will need|shopping list)\b", re.I)
END = re.compile(r"^\W*(method|instructions?|directions?|steps?|preparation|how to|notes?|follow|subscribe)\b", re.I)
SKIP_HOSTS = ("youtube.com", "youtu.be", "instagram.com", "facebook.com", "twitter.com", "x.com", "tiktok.com",
              "amazon.", "amzn.", "patreon.com", "discord.", "bit.ly", "linktr.ee")


def yt_desc(html):
    m = re.search(r'"shortDescription":"(.*?)","isCrawlable', html, re.S)
    if not m: return None, "YouTube recipe"
    try: desc = json.loads('"' + m.group(1) + '"')
    except ValueError: return None, "YouTube recipe"
    t = re.search(r"<title>(.*?)</title>", html)
    return desc, (t.group(1).replace(" - YouTube", "") if t else "YouTube recipe")[:150]


def desc_ingredients(desc):
    out, on = [], False
    for l in desc.splitlines():
        if not on:
            if HEAD.match(l):
                on = True; rest = HEAD.sub("", l).strip(" :-–")
                if rest and rest[0].isdigit(): out.append(rest)
            continue
        if END.match(l): break
        l = l.strip(" -•*▪–")
        if not l:
            if len(out) >= 3: break
            continue
        if len(l) < 120 and "http" not in l: out.append(l)
        if len(out) >= 60: break
    return out


def desc_links(desc):
    out = []
    for u in re.findall(r"https?://[^\s<>\"]+", desc):
        u = u.rstrip(".,);]")
        h = (urlparse(u).hostname or "").lower()
        if h and not any(x in h for x in SKIP_HOSTS) and u not in out: out.append(u)
    return out[:3]


def video_id(url):
    u = urlparse(url)
    if (u.hostname or "").endswith("youtu.be"): return u.path.strip("/")[:11] or None
    m = re.search(r"(?:[?&]v=|/shorts/|/embed/)([\w-]{11})", url)
    return m.group(1) if m else None


def _transcript(vid):
    """Returns (text, error_name). Picks English, else Hindi, else any available caption track."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi as Y
        tl = list(Y().list(vid))
        if not tl: return None, "NoTranscriptFound"
        pick = (next((t for t in tl if t.language_code.startswith("en")), None)
                or next((t for t in tl if t.language_code.startswith("hi")), None) or tl[0])
        return " ".join(s.text for s in pick.fetch()), None
    except Exception as e:
        return None, type(e).__name__


async def from_url(url, ip="?"):
    html = await fetch(url)
    host = (urlparse(url).hostname or "").lower()
    if not host.endswith(("youtube.com", "youtu.be")):
        r = parse_html(html)
        if r: return r
        raise ExtractError("Couldn't find a structured recipe at this URL. Please paste the recipe text instead.")
    desc, title = yt_desc(html)
    res, vid, reason = None, video_id(url), "could not read the video id"
    if desc:  # 1) description list, 2) recipe link in description  (unchanged text flow)
        lines = desc_ingredients(desc)
        if len(lines) >= 2: res = {"title": title, "servings": 4, "lines": lines, "source": "YouTube description"}
        else:
            for link in desc_links(desc):
                try: r = parse_html(await fetch(link))
                except ExtractError: continue
                if r: res = {**r, "source": f"recipe link in video description ({urlparse(link).hostname})"}; break
    if not res and vid:  # 3) transcript + Groq (unchanged)
        tr, terr = await asyncio.to_thread(_transcript, vid)
        print("transcript:", "ok" if tr else terr)
        if not tr: reason = f"no usable transcript ({terr}; the video may have no captions, or YouTube blocked this server)"
        elif not llm.KEY: reason = "AI extraction is not enabled on the server (GROQ_API_KEY is not set)"
        else:
            x = None
            try: x = await llm.extract_ingredients(tr)
            except Exception as ex:
                r = getattr(ex, "response", None); print("llm error:", type(ex).__name__, getattr(r, "status_code", None), (getattr(r, "text", "") or "")[:200])
                reason = "the AI step failed (check the server log; the key, model name or rate limit may be wrong)"
            else: reason = "the AI could not find a clear ingredient list in the spoken transcript, or the daily AI limit was reached"
            if x:
                res = {"title": title, "servings": x["servings"], "lines": x["lines"], "source": "YouTube transcript (AI-extracted)",
                       "warning": "AI-extracted from speech and may be wrong or incomplete. Check every line; set wrong ones to Skip."}
    # Text is sufficient (>=3 ingredient lines) -> done, Gemini NOT called. Without GEMINI_API_KEY behaviour is exactly as before.
    if res and (len(res["lines"]) >= 3 or not visual.ENABLED): return res
    if visual.ENABLED and vid:  # 4) visual fallback (no text) or supplement (incomplete text)
        try: return await visual.analyze(vid, html, ip, title, res)
        except visual.VisualError as e:
            print("visual:", e)
            if res: return {**res, "warning": f"Visual analysis unavailable ({e}); using text only."}
            raise ExtractError(f"Unable to visually analyze this video ({e}). Please try another video or provide the recipe manually.")
    if res: return res
    raise ExtractError(f"Couldn't get a recipe from this video: no ingredient list or recipe link in the description, and {reason}. "
                       "Please paste the recipe text instead.")
