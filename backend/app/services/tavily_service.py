import logging
import re
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.services.contact_extraction import is_own_website

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"

_SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "linkedin.com": "linkedin",
    "twitter.com": "twitter",
    "x.com": "twitter",
}


async def search(query: str, max_results: int = 5) -> list[dict]:
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        # Pro tier is the paid, "best data" tier — advanced search depth costs
        # more Tavily credits per call but returns more thorough, higher-quality
        # results than basic depth.
        "search_depth": "advanced",
        "max_results": max_results,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(TAVILY_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data.get("results", [])


async def discover_listing_pages(niche: str, city: str, country: str, max_results: int = 6) -> list[dict]:
    """Search for directory/listicle pages about this niche+city and pull back
    their full page content. Sites like Yellow Pages and Yelp block direct
    scraping (their bot-walls reject even a browser-like User-Agent without
    executing JS), but Tavily's own crawler already has the page indexed and
    hands it back to us as plain text/markdown — so instead of scraping those
    sites ourselves, we let Tavily do it and parse what it returns."""
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    payload = {
        "api_key": settings.tavily_api_key,
        "query": f"best {niche} in {city} {country} list directory contact",
        "search_depth": "advanced",
        "max_results": max_results,
        "include_raw_content": True,
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.post(TAVILY_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data.get("results", [])


def _social_platform_for_url(url: str) -> Optional[str]:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return _SOCIAL_DOMAINS.get(host)


_STOPWORDS = {"the", "and", "for", "inc", "llc", "ltd", "restaurant", "shop", "store"}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOPWORDS]


def _is_relevant(business_name: str, city: str, result: dict) -> bool:
    """A generic 'business name + city + facebook/instagram/linkedin' search
    can surface completely unrelated pages that just happen to share a word
    with the business name — a common business-name phrase (e.g. "Officers
    Mess", a generic term for a military dining hall) will genuinely appear in
    unrelated government reports or social posts about someone else entirely.
    A single shared word isn't enough signal; require either the full business
    name as a phrase, or a name word *and* the city together."""
    title = (result.get("title") or "").lower()
    url = (result.get("url") or "").lower()
    haystack = f"{title} {url}"

    name_lower = business_name.lower().strip()
    if name_lower and name_lower in haystack:
        return True

    name_words = _words(business_name)
    city_words = _words(city)
    if not name_words:
        return True
    if not any(w in haystack for w in name_words):
        return False
    # Name word matched — still require the city too, unless there's no usable
    # city signal to check against.
    return not city_words or any(w in haystack for w in city_words)


def _domain_matches_business(business_name: str, url: str) -> bool:
    """A generic niche+city search for "official website" very often surfaces
    third-party review sites, food blogs, and directory aggregators instead of
    the business's own site — the business name shows up in the URL *path*
    ("foodiespakistan.pk/karachi/kolachi-restaurant-...") but the *domain*
    belongs to someone else entirely. Scraping that domain would attribute the
    aggregator's own contact details to this business. Requiring a name word
    in the domain itself is a strict filter, but a missing website is far
    better than a wrong one."""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    domain_words = re.findall(r"[a-z0-9]+", host)
    name_words = _words(business_name)
    if not name_words:
        return True
    return any(nw in dw or dw in nw for nw in name_words for dw in domain_words if len(dw) > 2)


async def find_website_url(business_name: str, city: str, country: str) -> Optional[str]:
    """Tavily's only job in the contact-enrichment pipeline: find a business's
    official website URL. Search-result snippets are too shallow and often
    stale for reliably pulling email/phone/social links out directly — once we
    have the URL, a real headless-browser scrape (browser_scraper_service)
    visits the site itself and reads whatever it actually publishes."""
    try:
        results = await search(f"{business_name} {city} {country} official website", max_results=5)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.warning("Tavily website lookup failed for %s: %s", business_name, exc)
        return None

    for result in results:
        if not _is_relevant(business_name, city, result):
            continue
        url = result.get("url", "")
        if not is_own_website(url) or _social_platform_for_url(url):
            continue
        if _domain_matches_business(business_name, url):
            return url
    return None
