"""DuckDuckGo web search — a free, no-API-key companion to Tavily.

Everywhere the codebase searches the web (the discovery URL-finder agent and the
enrichment fallbacks for websites, contacts and social profiles) it now asks both
Tavily and DuckDuckGo. DuckDuckGo costs nothing per call, so it is the cheap bulk
source; Tavily's raw-content / listing-page support covers what DuckDuckGo can't.

We hit DuckDuckGo's public HTML endpoint and parse the markup with the stdlib
HTMLParser — no third-party scraping dependency. This endpoint is unofficial and
may rate-limit or serve different markup, so every function here degrades to a
best-effort result (empty list / None) instead of raising.
"""
import logging
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.services.tavily_service import _is_relevant, _social_platform_for_url
from app.services.contact_extraction import is_own_website

logger = logging.getLogger(__name__)

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
DDG_TIMEOUT = 15.0
DDG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _real_url(href: str) -> str:
    """DuckDuckGo wraps each result link in a redirect
    (https://duckduckgo.com/l/?uddg=<encoded-target>). Unwrap it to the real
    destination; a bare/relative href is unescaped and scheme-completed."""
    if not href:
        return ""
    href = href.replace("&amp;", "&")
    if "/l/?uddg=" in href:
        parsed = urlparse(href)
        if "duckduckgo.com" in parsed.netloc:
            target = parse_qs(parsed.query).get("uddg", [None])[0]
            if target:
                return unquote(target)
            return ""
    if href.startswith("//"):
        href = "https:" + href
    return unquote(href)


class _ResultParser(HTMLParser):
    """Minimal parser for html.duckduckgo.com result pages. Collects each
    `.result__a` anchor (title + real URL) together with its `.result__snippet`
    text. Unknown markup is ignored; the parser never raises."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict] = []
        self._current: Optional[dict] = None
        self._in_title = False
        self._in_snippet = False

    def handle_starttag(self, tag, attrs) -> None:
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "a" and "result__a" in classes:
            if self._current is not None:
                self.results.append(self._current)
            self._current = {"title": "", "url": _real_url(attrs.get("href", "")), "content": ""}
            self._in_title = True
        elif self._current is not None and "result__snippet" in classes:
            self._in_snippet = True

    def handle_data(self, data) -> None:
        if self._current is None:
            return
        if self._in_title:
            self._current["title"] += data
        elif self._in_snippet:
            self._current["content"] += data

    def handle_endtag(self, tag) -> None:
        if tag == "a":
            self._in_title = False
            self._in_snippet = False

    def close(self) -> None:
        super().close()
        if self._current is not None:
            self.results.append(self._current)
            self._current = None


async def search(query: str, max_results: int = 8) -> list[dict]:
    """Return up to `max_results` DDG results as {title, url, content}. Never
    raises — on any transport/parse failure it logs and returns []."""
    try:
        async with httpx.AsyncClient(timeout=DDG_TIMEOUT, headers=DDG_HEADERS, follow_redirects=True) as client:
            resp = await client.get(DDG_HTML_URL, params={"q": query})
            resp.raise_for_status()
            text = resp.text
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("DuckDuckGo search failed for %r: %s", query, exc)
        return []

    parser = _ResultParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:  # HTMLParser never raises on well-formed maj
        logger.warning("DuckDuckGo result parse failed for %r: %s", query, exc)
        return []
    return [r for r in parser.results if r.get("url")][:max_results]


async def find_website_url(business_name: str, city: str, country: str) -> Optional[str]:
    """Find a business's official website the same way Tavily does — first
    search result whose URL is a real business site (not social/directory/maps)
    and whose domain plausibly matches the business name."""
    try:
        results = await search(f"{business_name} {city} {country} official website", max_results=6)
    except Exception as exc:
        logger.warning("DuckDuckGo website lookup failed for %s: %s", business_name, exc)
        return None

    for result in results:
        if not _is_relevant(business_name, city, result):
            continue
        url = result.get("url", "")
        if not url or not is_own_website(url) or _social_platform_for_url(url):
            continue
        if _domain_matches_business(business_name, url):
            return url
    return None


def _domain_matches_business(business_name: str, url: str) -> bool:
    from app.services.tavily_service import _domain_matches_business

    return _domain_matches_business(business_name, url)


async def enrich_business(business_name: str, city: str, country: str, max_results: int = 8) -> list[dict]:
    """DuckDuckGo half of the contact web-search fallback. Mirrors Tavily's
    return shape so callers can treat both engines uniformly."""
    query = f'"{business_name}" {city} {country} contact email phone address'
    results = await search(query, max_results=max_results)
    return [r for r in results if _is_relevant(business_name, city, r)]


async def find_social_links(business_name: str, city: str, country: str = "") -> dict[str, str]:
    query = f'"{business_name}" {city} {country} instagram facebook linkedin profile'
    socials: dict[str, str] = {}
    for result in await search(query, max_results=8):
        url = result.get("url", "")
        platform = _social_platform_for_url(url)
        if not platform or platform in socials:
            continue
        if _is_relevant(business_name, city, result):
            socials[platform] = url
        if len(socials) >= 4:
            break
    return socials