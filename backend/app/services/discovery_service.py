"""Two-phase web lead discovery.

Phase 1 (URL finder) lives here: a niche + city/country query is turned into a
list of *real* candidate businesses found on the open web — either their own
website (which Phase 2 crawls) or a website-less business surfaced through
directory/listicle pages. OpenStreetMap/Overpass is gone; every candidate comes
from Tavily + DuckDuckGo search results, so nothing is fabricated.

Phase 2 (crawler) is enrichment_pipeline: each candidate's website is scraped
for email/phone/socials, and Tavily + DuckDuckGo contact search fills the gaps
for businesses that have no website at all.
"""
import logging
import re
from typing import Optional
from urllib.parse import urlparse

from app.services import duckduckgo_service, listing_extraction_service, tavily_service
from app.services.contact_extraction import is_own_website
from app.services.tavily_service import _social_platform_for_url

logger = logging.getLogger(__name__)


class DiscoveryUnavailableError(Exception):
    pass


# The URL-finder agent runs these query templates against BOTH engines. The
# "official website" phrasing is intentionally first: it surfaces a business's
# own domain directly, which is exactly what the Phase 2 crawler wants. The
# other phrasings over-fetch so enough real candidates survive de-duplication
# to fill the requested count.
def _build_queries(niche: str, city: str, country: str) -> list[str]:
    return [
        f"official website for {niche} in {city} {country}",
        f"{niche} in {city} {country}",
        f"best {niche} in {city} {country}",
        f"{niche} {city} {country} email phone contact",
    ]


# Aggregator/directory host fragments to reject even when the domain is not in
# contact_extraction.NON_WEBSITE_DOMAINS (which is tuned for the enrichment
# scrape, not discovery). A result on one of these is never the business's own
# website.
_DIRECTORY_MARKERS = (
    "yellowpages", "yelp", "justdial", "tripadvisor", "cybo", "hotfrog",
    "bizapedia", "zoominfo", "darpak", "foodiespakistan", "cybo",
)

_MAX_TAVILY_LISTING_PAGES = 4
_TAVILY_LISTING_MIN_CONTENT_CHARS = 500


def _plausible_website(url: str) -> bool:
    """A real business website: not a social/maps/directory domain and not on
    the directory-marker list. `is_own_website` covers the known blocklist; the
    markers catch aggregators that blocklist doesn't know about."""
    if not url or not is_own_website(url) or _social_platform_for_url(url):
        return False
    host = urlparse(url).netloc.lower()
    return not any(marker in host for marker in _DIRECTORY_MARKERS)


def _words_of(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _looks_on_theme(result: dict, niche: str, city: str) -> bool:
    """Soft relevance filter: a result should mention the niche or the city
    somewhere in its title/url/snippet, otherwise it's off-topic for discovery
    (e.g. a generic name match from another industry entirely)."""
    hay = " ".join(str(result.get(k) or "") for k in ("title", "url", "content"))
    hay_words = _words_of(hay)
    return bool(_words_of(niche) & hay_words) or bool(_words_of(city) & hay_words)


_REMOVE_NAME_SUFFIX_RE = re.compile(
    r"\s*(official\s*website|home|web\s*site|contact\s*us?)\s*$", re.IGNORECASE
)
_NAME_SEPARATORS_RE = re.compile(r"\s*[|\u2013\u2014\u2022\u00b7]\s*")

_TLD_SUFFIXES = {
    "com", "co", "org", "net", "io", "me", "pk", "uk", "us", "ae", "sa",
    "ca", "au", "nz", "de", "fr", "it", "es", "mx", "in", "bd", "lk", "eg",
}


def _domain_token_name(url: str) -> Optional[str]:
    host = urlparse(url).netloc.lower().removeprefix("www.").split(":")[0]
    parts = re.split(r"[.-]", host)
    while parts and parts[-1] in _TLD_SUFFIXES:
        parts.pop()
    if parts and parts[0] in ("www", "ww2"):
        parts.pop(0)
    words = [p for p in parts if len(p) > 1]
    return " ".join(w.capitalize() for w in words) if words else None


def _clean_business_name(title: str, url: str) -> Optional[str]:
    """Derive a business name from a search-result title, falling back to the
    site's own domain. Titles usually read "Sakura Dental Studio – Dental
    Clinic in Karachi | Official Website"."""
    name = ""
    if title:
        first = _NAME_SEPARATORS_RE.split(title)[0].strip()
        name = _REMOVE_NAME_SUFFIX_RE.sub("", first).strip()
    if len(name) < 2:
        name = _domain_token_name(url) or ""
    return " ".join(re.findall(r"[a-zA-Z0-9&']+", name)) or None


def _candidate_from_result(result: dict, niche: str, city: str) -> Optional[dict]:
    url = (result.get("url") or "").strip()
    if not _plausible_website(url):
        return None
    if not _looks_on_theme(result, niche, city):
        return None
    name = _clean_business_name(result.get("title") or "", url)
    if not name:
        return None
    return {
        "name": name,
        "website": url,
        "address": city,
        "industry": niche.strip().title(),
        "social_links": {},
        "source": "web_search",
    }


def _name_key(item: dict) -> str:
    return re.sub(r"[^a-z0-9]+", "", (item.get("name") or "").lower())


def _website_key(item: dict) -> str:
    return (item.get("website") or "").lower().rstrip("/")


def _candidates_seen_add(candidates: list[dict], seen_names: set, seen_websites: set, item: dict) -> None:
    name_key = _name_key(item)
    website_key = _website_key(item)
    if not name_key:
        return
    if name_key in seen_names:
        return
    if website_key and website_key in seen_websites:
        return
    seen_names.add(name_key)
    if website_key:
        seen_websites.add(website_key)
    candidates.append(item)


async def _find_direct_websites(niche: str, city: str, country: str) -> list[dict]:
    """Search both engines with the query set and keep direct business-website
    candidates. Returns [] on total failure so callers can tell providers apart
    from 'no results' — provider-level failures are logged here."""
    queries = _build_queries(niche, city, country)
    candidates: list[dict] = []
    engaged = False

    try:
        for query in queries[:3]:
            results = await tavily_service.search(query, max_results=8)
            for result in results:
                item = _candidate_from_result(result, niche, city)
                if item:
                    candidates.append(item)
        engaged = True
    except Exception as exc:
        logger.warning("Tavily URL-finder search failed for %s in %s: %s", niche, city, exc)

    try:
        for query in queries:
            results = await duckduckgo_service.search(query, max_results=10)
            for result in results:
                item = _candidate_from_result(result, niche, city)
                if item:
                    candidates.append(item)
        engaged = True
    except Exception as exc:
        logger.warning("DuckDuckGo URL-finder search failed for %s in %s: %s", niche, city, exc)

    if not engaged:
        raise DiscoveryUnavailableError(
            "Web search is temporarily unavailable. Please try again in a moment."
        )
    return candidates


async def _find_website_less(
    niche: str, city: str, country: str, needed: int
) -> list[dict]:
    """Website-less businesses from Tavily's directory/listicle pages: real
    businesses that simply don't run their own site, surfaced through the raw
    page content + an AI extraction pass."""
    if needed <= 0:
        return []
    try:
        pages = await tavily_service.discover_listing_pages(niche, city, country, max_results=6)
    except Exception as exc:
        logger.warning("Tavily listing discovery failed for %s in %s: %s", niche, city, exc)
        return []

    dir_pages = [
        page for page in pages
        if len(page.get("raw_content") or "") > _TAVILY_LISTING_MIN_CONTENT_CHARS
    ][:_MAX_TAVILY_LISTING_PAGES]
    if not dir_pages:
        return []

    collected: list[dict] = []
    per_page = max(5, needed // len(dir_pages))
    for page in dir_pages:
        try:
            businesses = await listing_extraction_service.extract_businesses(
                niche, city, page["raw_content"], max_items=per_page
            )
        except Exception as exc:
            logger.warning("Listing extraction failed for a %s page in %s: %s", niche, city, exc)
            continue
        for business in businesses:
            collected.append({
                **business,
                "address": business.get("address") or city,
                "industry": niche.strip().title(),
                "social_links": {},
                "source": "web_search",
            })
            if len(collected) >= needed:
                return collected
    return collected


async def discover_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Phase 1 URL finder. Returns up to `limit` unique, real businesses for a
    niche in a city/country. Direct-website candidates are preferred; website-
    less businesses fill the remaining slots. Never fabricates a lead and never
    returns the same business twice."""
    if limit < 1:
        return []

    direct = await _find_direct_websites(niche, city, country)
    candidates: list[dict] = []
    seen_names: set = set()
    seen_websites: set = set()

    for item in direct:
        _candidates_seen_add(candidates, seen_names, seen_websites, item)
        if len(candidates) >= limit:
            return candidates

    if len(candidates) < limit:
        website_less = await _find_website_less(niche, city, country, needed=limit - len(candidates))
        for item in website_less:
            _candidates_seen_add(candidates, seen_names, seen_websites, item)
            if len(candidates) >= limit:
                break

    # Most usable first (a website beats phone beats nothing) so the returned
    # slice is the strongest real candidates available.
    candidates.sort(
        key=lambda r: sum(bool(r.get(field)) for field in ("website", "phone", "email")),
        reverse=True,
    )
    return candidates[:limit]