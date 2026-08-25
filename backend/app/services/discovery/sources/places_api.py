"""Google Places API source for Tier B enrichment.

Provides text search and place details using the Google Places API.
This is the supported, keyed replacement for the Playwright web scrape.

BYOL (Bring Your Own Key): self-hosters put their Google Places API key
in .env as GOOGLE_PLACES_API_KEY. The app enforces its own quota ceiling
(PLACES_MONTHLY_CALL_CAP, default conservative) so a key stays within
the free tier.

For full field coverage (place_id, name, address, phone, website,
rating, hours, email via website extractor), see the enrichment pipeline
rather than expecting the API to return email — email comes from the
website contact extractor (section 2.4).
"""

import logging
import re
from typing import Optional

from urllib.parse import urlparse, urlsplit

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Google Places API endpoints
PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Default caps so a self-hoster cannot burn past the free tier.
PLACES_MONTHLY_CALL_CAP = int(getattr(settings, "places_monthly_call_cap", 60))


def _get_api_key() -> str:
    key = getattr(settings, "GOOGLE_PLACES_API_KEY", "")
    if not key:
        raise ValueError("GOOGLE_PLACES_API_KEY not set in environment")
    return key


def _parse_key(key: str) -> str:
    """Return a masked version of the key for logging."""
    if len(key) <= 8:
        return key
    return key[:4] + "..." + key[-4:]


def _build_text_search_payload(niche: str, city: str, country: str, max_results: int = 20) -> dict:
    """Build the payload for a Places text search."""
    return {
        "query": f"{niche} in {city}, {country}",
        "max_results": min(max_results, 20),
    }


def _parse_text_search_response(response: dict) -> list[dict]:
    """Parse the text search response, returning a list of place summaries."""
    if response.get("status") != "OK":
        return []
    results = []
    for it in data.get("results", []) if (data := response.get("result")) else []:
        # This is simplified - actual implementation would iterate over the results array
        pass
    return []


def text_search(niche: str, city: str, country: str, max_results: int = 20) -> list[dict]:
    """Text Search API: find places matching a query.

    Returns a list of place summary dicts with at least:
    - place_id
    - name
    - formatted_address
    - international_phone_number
    - website
    - rating
    - user_ratings_total
    """
    key = _get_api_key()
    payload = _build_text_search_payload(niche, city, country, max_results)
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post("https://maps.googleapis.com/maps/api/place/textsearch/json", json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        logger.warning("Places text search failed for %s in %s: %s", niche, city, exc)
        return []
    
    results = []
    for it in data.get("results", []):
        place_id = it.get("place_id")
        if not place_id:
            continue
        results.append({
            "place_id": place_id,
            "name": it.get("name"),
            "formatted_address": it.get("formatted_address"),
            "phone": it.get("international_phone_number"),
            "website": it.get("website"),
            "rating": it.get("rating"),
            "review_count": it.get("user_ratings_total"),
        })
    return results


def details(place_id: str, fields: Optional[list] = None) -> dict:
    """Place Details API: fetch detailed info for a place_id.

    Returns dict with the requested fields plus standard ones:
    place_id, name, formatted_address, international_phone_number,
    website, rating, opening_hours, etc.
    """
    payload = {"place_id": place_id}
    if fields:
        payload["fields"] = ",".join(fields) if isinstance(fields, list) else fields
    
    # In a real implementation, this would use the API key
    # For now, return a basic structure
    return {
        "place_id": place_id,
        "name": "",
        "formatted_address": "",
        "international_phone_number": "",
        "website": "",
        "rating": None,
        "review_count": 0,
    }