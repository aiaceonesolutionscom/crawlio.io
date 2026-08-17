"""Tavily web search — an opt-in, last-resort top-up source.

Google Maps + OSM/Overpass + free directories are the primary sources; this
module only runs when discovery_service finds their combined, validated
result count still short of what was requested (thinner markets outside the
biggest cities).

How this produces *real* leads:

- Tavily's results carry a `content` snippet of the actual page. We extract
  phone / email / address / social links out of that text with the same regex
  scoring used everywhere else in discovery (contact_extraction) — nothing is
  invented or guessed, it's read off the real page copy.
- A result whose URL is the business's OWN website becomes a {name, website}
  candidate; the website is then scraped by enrichment_pipeline.py for the
  remaining fields (email MX-verified, phone normalized), exactly like every
  other source.
- A result that is a **directory / portal listing** (a business listed on
  oladoc.com, instacare.pk, marham.pk, a local yellow pages, etc.) is NOT
  dropped: those businesses are exactly the "no website yet" prospects. The
  listing's own name + phone + address are extracted and the record carries
  website=None so it reads as a real local business without an online
  presence. A listing page is only accepted when its content contains an
  actual phone number — a category page that lists many businesses has no
  single phone and is filtered out that way.

Business names go through the same SEO-spam cleanup as Google Maps listings
("|" separators, site-name suffixes, "Best X in Y" taglines, portal copy).

Never raises — any failure (missing/bad key, rate limit, timeout, no
results) returns [] so a search never breaks because this optional source is
unavailable.
"""
import asyncio
import logging
import re
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.integration_runtime import api_key
from app.services.discovery.contact_extraction import (
    best_email,
    best_phone,
    clean_business_name,
    find_social_links,
    is_own_website,
)


logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
TIMEOUT = 20.0

# Domains Tavily is told to never return. Deliberately does NOT include
# DIRECTORY_DOMAINS: a business listed on oladoc.com / marham.pk / instacare.pk
# is exactly the "no website yet" prospect this module exists to surface, so
# those must still reach us (the client-side is_own_website() check then treats
# the URL as a listing, not the business's own site). What we do exclude is the
# pure junk that can never be a single business: social pages, maps/geo and
# generic aggregators.
_EXCLUDE_DOMAINS = sorted({
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "maps.google.com", "goo.gl", "yelp.com",
    "tripadvisor.com", "wikipedia.org", "foursquare.com", "waze.com",
    "bing.com", "openstreetmap.org", "trustpilot.com", "glassdoor.com",
    "capterra.com", "g2.com", "clutch.co",
})

# Phrases that mark a title as a category/portal page rather than one business.
_JUNK_NAME_MARKERS = (
    "buy and sell", "sell properties", "property for sale", "properties in",
    "top 10", "top 5", "top 100", "best 10", "list of", "directory", "listing",
    "classified", "portal", "marketplace", "find your", "search results",
    "the complete guide", "everything you need", "book online appointment",
    "book appointment", "compare", "near you", "read more",
)
# Leading words that mean a title is a category/tagline, not a business name.
_JUNK_NAME_PREFIXES = (
    "best ", "top ", "the best ", "how to ", "where to ", "find ", "search ",
    "home", "about", "contact us", "book ", "appointment", "faq", "list ",
)

# Street-ish words used to pull an address line out of a content snippet.
# Deliberately does NOT include bare "near"/"opposite"/"beside": those appear in
# SEO taglines and the search query itself ("best dental clinic near me") and
# would turn query text into a fake address. A real street address almost always
# carries one of these concrete markers.
_ADDRESS_WORDS = (
    "road", "street", "st.", "lane", "avenue", "block", "plaza", "colony",
    "house no", "house #", "house no.", "office", "shop no", "shop #",
    "society", "gulberg", "cantt", "dha", "model town", "market", "phase",
    "garden", "main boulevard", "main road", "street no", "street number",
    "building", "mall", "tower", "flying coach", "check post", "shopping",
)


def _clean_web_name(title: str) -> str:
    """Turn a search-result title into a plausible business name. Strips
    site-name suffixes ("Foo Clinic | Zameen.com"), tagline-after-colon
    ("Rahman & Rahman Dental Clinic: Best Dentists in Lahore"), and trailing
    city/duplicate text, then rejects portal/category copy outright."""
    name = (title or "").strip()
    if not name:
        return ""

    # Cut site-name suffixes first: "Name — Zameen.com", "Name | Zameen.com".
    for sep in (" — ", " – ", " - ", " | ", " » ", " - "):
        if sep in name:
            left, _, _ = name.partition(sep)
            if left.strip():
                name = left.strip()
            break

    # Tagline after a colon is common on real business sites:
    # "Rahman & Rahman Dental Clinic: Best Dentists in DHA, Lahore"
    # Keep the part before ":" only when it stands alone as a business name
    # (not itself junk like "Best Dentist in Lahore").
    if ":" in name:
        head, _, tail = name.partition(":")
        head = head.strip()
        tail = tail.strip()
        if len(head.split()) >= 2 and not _is_junk_name(head):
            name = head
        elif tail:
            # "Home - Best Dentist" style: strip leading junk prefix from tail.
            name = tail.strip(" -")

    name = name.rstrip(" ,.-")
    lowered = name.lower()
    if any(marker in lowered for marker in _JUNK_NAME_MARKERS):
        return ""
    if _is_junk_name(name):
        return ""

    # Strip a trailing ", Lahore" / " (Lahore)" / "- Lahore" city fragment.
    name = re.sub(r"\s*[,(/-]\s*[A-Za-z]+(?:\s+[A-Za-z]+){0,2}\s*\)?\s*$", "", name).strip(" ,-")
    if not name:
        return ""
    if len(name.split()) < 2:
        return ""
    return clean_business_name(name).strip()


def _is_junk_name(name: str) -> bool:
    lowered = (name or "").strip().lower()
    if not lowered or len(lowered) < 4:
        return True
    return lowered.startswith(_JUNK_NAME_PREFIXES)


def _name_matches_content(name: str, content: str) -> bool:
    """True when the cleaned name appears in the snippet, or the snippet
    carries at least one distinctive (>=5 char, non-generic) word of it.
    Tavily can serve a title whose snippet belongs to a different business on
    the same site; this guards against that mismatch becoming a fake lead."""
    name_l = (name or "").lower()
    content_l = (content or "").lower()
    if not name_l or not content_l:
        return True
    if name_l in content_l:
        return True
    distinctive = [
        w for w in name_l.replace("&", " ").replace(",", " ").split()
        if len(w) >= 5 and w not in {"dental", "clinic", "center", "centre",
                                     "specialist", "care", "hospital", "pk"}
    ]
    return any(w in content_l for w in distinctive)


def _extract_address(content: str, city: str) -> str:
    """Best-effort street address from a content snippet: prefer a line that
    carries a real street marker + the city, then any line with a real street
    marker. Lines that look like the search query ("best dental clinic near
    me ..."), pure nav copy, or portal boilerplate are never treated as an
    address."""
    if not content:
        return ""
    lines = [ln.strip() for ln in re.split(r"[|\n]{1,2}", content) if ln and ln.strip()]
    city_l = city.strip().lower()
    street_lines: list[str] = []
    for line in lines:
        if len(line) < 8 or len(line) > 160:
            continue
        lowered = line.lower()
        # Query/tagline/boilerplate markers — never an address.
        if any(phrase in lowered for phrase in (
            "near me", "best dental", "best clinic", "top ", "for appointments",
            "scheduling", "consultation", "call ", "contact us", "book appointment",
            "home", "about us", "privacy policy", "terms",
        )):
            continue
        if any(word in lowered for word in _ADDRESS_WORDS):
            street_lines.append(line)

    for line in street_lines:
        if city_l and city_l in line.lower():
            return line.strip()
    if street_lines:
        return street_lines[0].strip()
    return ""


def _parse_result(result: dict, city: str, country: str, country_code: str) -> dict:
    """Turn one Tavily result into a lead-shaped record. Own-website results
    keep the website; directory/portal results become no-website records with
    the contacts the listing actually published (a listing without a phone is
    a category page and is rejected here)."""
    url = (result.get("url") or "").strip()
    title = (result.get("title") or "").strip()
    content = (result.get("content") or "").strip()
    if not url or not title:
        return {}

    own_website = is_own_website(url)

    # A listing page without any reachable phone in its copy is a category
    # page ("Best Dentists in Lahore", "Top 5 clinics") listing many businesses
    # — not one business. Only accept a directory record when we actually got
    # a phone for the listed business.
    if not own_website:
        phone = best_phone(content, country_code)
        if not phone:
            return {}

    name = _clean_web_name(title)
    if not name:
        return {}

    # Tavily occasionally pairs a title with the wrong page's snippet (a
    # contact page whose scraped content belongs to an unrelated business).
    # The cleaned name must show up in the snippet, or the snippet must at
    # least carry a distinctive word of it, or the record is dropped.
    if content and not _name_matches_content(name, content):
        return {}

    # Geo sanity: the snippet (or the address we can extract from it) must
    # place the business in the requested city or at least its country.
    # Otherwise a foreign lookalike ("Noor Dental Clinic" Toronto for a
    # Karachi search) slips through as a fake lead.
    address = _extract_address(content, city)
    city_l = city.strip().lower()
    country_l = country.strip().lower()
    content_l = (content or "").lower()
    if content_l and city_l not in content_l and country_l not in content_l:
        if not (address and (city_l in address.lower() or country_l in address.lower())):
            return {}

    record: dict = {
        "name": name,
        "phone": None,
        "email": None,
        "website": url if own_website else None,
        "address": address,
        "source": "web_search",
        "industry": "",
        "social_links": {},
    }

    if content:
        email = best_email(content, record["website"])
        if email:
            record["email"] = email
        if record["phone"] is None:
            record["phone"] = best_phone(content, country_code)
        socials = find_social_links(content)
        if socials:
            record["social_links"] = socials

    return record


def _queries(niche: str, city: str, country: str) -> list[str]:
    """Several phrasings, run concurrently, so the niche+city is covered even
    when Tavily's ranking favors one phrasing over another."""
    return [
        f"{niche} in {city}, {country} contact phone email address",
        f"{niche} businesses in {city}, {country} phone number",
        f"{niche} in {city} with phone number and address",
    ]


async def _run_query(client: httpx.AsyncClient, query: str, max_results: int) -> list[dict]:
    try:
        resp = await client.post(
            TAVILY_URL,
            json={
                "api_key": api_key("tavily_api_key"),
                "query": query,
                "search_depth": "advanced",
                "max_results": max_results,
                "exclude_domains": _EXCLUDE_DOMAINS,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Tavily search failed for %r: %s", query, exc)
        return []
    return data.get("results", []) or []


async def find_extra_businesses(
    niche: str, city: str, country: str, limit: int, country_code: str = "PK"
) -> list[dict]:
    """Return up to `limit` extra candidate records (name + any real contact
    fields Tavily's page snippets actually carry). Own-website candidates may
    carry only a website; directory-listed candidates carry a phone and
    website=None. Never invents a field."""
    if not settings.tavily_enabled or not api_key("tavily_api_key") or limit < 1:
        return []

    max_results = max(1, min(limit, settings.tavily_max_results))
    per_query = max(1, (max_results + len(_queries(niche, city, country)) - 1) // len(_queries(niche, city, country)))

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            all_results = await asyncio.gather(
                *(_run_query(client, q, per_query) for q in _queries(niche, city, country))
            )
    except Exception as exc:
        logger.warning("Tavily top-up failed for %s in %s: %s", niche, city, exc)
        return []

    records: list[dict] = []
    seen: set[tuple] = set()
    for results in all_results:
        for result in results:
            record = _parse_result(result, city, country, country_code)
            if not record or not record.get("name"):
                continue
            dedup_key = (record["name"].lower(), record.get("phone") or "", record.get("website") or "")
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            record["industry"] = niche.strip().title()
            records.append(record)
            if len(records) >= limit:
                return records

    return records
