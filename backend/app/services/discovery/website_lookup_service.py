"""Free, keyless business-website lookup via a chain of plain-HTML search
engines (DuckDuckGo -> Bing -> Google).

The discovery sources that are thin on contact data (OSM, Geoapify, Nominatim,
directories) usually still return the business *name* and *address*. This module
turns that name into the business's own website URL by searching free HTML
search endpoints (no API key, no billing) and taking the first result that
looks like the business's own site.

Engines are tried in order so that when one is blocked, rate-limited, or
unreachable (DuckDuckGo frequently drops the plain-HTML endpoint) the next one
still answers.

Safety rules, load-bearing:
- Only the business's OWN website is returned — directory/portal/social/maps
  domains are filtered out via contact_extraction.is_own_website, so we never
  attribute a listing page as a business site.
- No contact data is invented here: the returned URL is then scraped by the
  existing enrichment pipeline (email MX-verified, phone normalized) exactly
  like every other source.
- Never raises — any failure (block, timeout, no results, markup change)
  returns None so a broken lookup can never fail a discovery search.
"""
import base64
import logging
import re
from typing import Callable, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.services.discovery.contact_extraction import is_own_website

logger = logging.getLogger(__name__)

DDG_URL = "https://html.duckduckgo.com/html/"
BING_URL = "https://www.bing.com/search"
GOOGLE_URL = "https://www.google.com/search"

MAX_RESULTS = 6

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

# DuckDuckGo HTML wraps organic results in anchors like
#   <a rel="nofollow" class="result__a" href="...">Title</a>
_RESULT_A_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
# Bing puts organic results in <li class="b_algo"> blocks; the first <a> is the
# direct (unwrapped) destination URL.
_BING_RE = re.compile(
    r'<li[^>]+class="b_algo"[^>]*>.*?<h2[^>]*>.*?<a[^>]+href="([^"]+)"',
    re.IGNORECASE | re.DOTALL,
)
# Google wraps organic results as /url?q=<encoded>. Match the encoded target.
_GOOGLE_URL_RE = re.compile(r'href="/url\?q=([^&"<>]+)', re.IGNORECASE)


def _parse_href(href: str) -> Optional[str]:
    """Search engines wrap redirects (e.g. DDG /l/?uddg=<encoded>, Google
    /url?q=<encoded>, Bing /ck/a?u=<base64url>). Unwrap to the real target;
    also accept a plain direct URL."""
    if not href:
        return None
    href = href.replace("&amp;", "&")
    target = href
    if "uddg=" in href:
        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        if query.get("uddg") and query["uddg"][0]:
            target = query["uddg"][0]
    elif "ck/a" in href:
        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        if query.get("u") and query["u"][0]:
            try:
                raw = query["u"][0]
                padded = raw + "=" * (-len(raw) % 4)
                decoded = base64.urlsafe_b64decode(padded.encode()).decode("utf-8", "ignore")
                if decoded.startswith(("http://", "https://")):
                    target = decoded
            except (ValueError, KeyError):
                pass
    target = unquote(target).strip()
    if not target:
        return None
    if target.startswith("//"):
        target = "https:" + target
    if not target.startswith(("http://", "https://")):
        return None
    return target


def _ddg_parse(html: str) -> List[str]:
    return [m.group(1) for m in _RESULT_A_RE.finditer(html)]


def _bing_parse(html: str) -> List[str]:
    return _BING_RE.findall(html)


def _google_parse(html: str) -> List[str]:
    return _GOOGLE_URL_RE.findall(html)


#: (name, url, query-builder, html parser, per-engine timeout)
Engine = tuple[str, str, Callable[[str], dict], Callable[[str], List[str]], float]

def _ddg_params(query: str) -> dict:
    return {"q": query}


def _bing_params(query: str) -> dict:
    return {"q": query, "setlang": "en", "count": "10"}


def _google_params(query: str) -> dict:
    return {"q": query, "hl": "en", "num": "10"}


DDG_ENGINE: Engine = (DDG_URL, "duckduckgo", _ddg_params, _ddg_parse, 6.0)
BING_ENGINE: Engine = (BING_URL, "bing", _bing_params, _bing_parse, 10.0)
GOOGLE_ENGINE: Engine = (GOOGLE_URL, "google", _google_params, _google_parse, 10.0)

#: Engines are consulted in order until one yields an own-website result.
#: Tests can monkeypatch this list to keep lookups hermetic.
ENGINES: List[Engine] = [DDG_ENGINE, BING_ENGINE, GOOGLE_ENGINE]


async def _run_engine(
    client: httpx.AsyncClient, engine: Engine, query: str, name: str
) -> Optional[str]:
    url, label, params_fn, parse_fn, timeout = engine
    try:
        resp = await client.get(url, params=params_fn(query), timeout=timeout)
        if resp.status_code >= 400:
            logger.info("Website lookup %s returned %d for %s", label, resp.status_code, name)
            return None
        html = resp.text
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Website lookup %s failed for %s: %s", label, name, exc)
        return None

    seen_hosts: set[str] = set()
    for raw in parse_fn(html):
        href = _parse_href(raw)
        if not href or not is_own_website(href):
            continue
        host = urlparse(href).netloc.lower().removeprefix("www.")
        if host in seen_hosts:
            continue
        seen_hosts.add(host)
        logger.info("Website lookup %s found %s -> %s", label, name, href)
        return href
    return None


async def find_business_website(name: str, city: str, country: str) -> Optional[str]:
    """Search the engine chain for a business name and return the first result
    that is the business's own website (own-domain only, directories/social/
    maps filtered out). Returns None when nothing suitable is found or every
    lookup fails — never raises."""
    query = f'"{name.strip()}" {city.strip()}, {country.strip()}'
    async with httpx.AsyncClient(timeout=10.0, headers=HEADERS, follow_redirects=True) as client:
        for engine in ENGINES:
            result = await _run_engine(client, engine, query, name)
            if result:
                return result
    return None
