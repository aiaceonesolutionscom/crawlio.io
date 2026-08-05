import logging
import re
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# Addresses that show up in search snippets but aren't real business contacts.
EMAIL_BLOCKLIST_DOMAINS = {"sentry.io", "example.com", "wixpress.com", "godaddy.com"}


async def search(query: str, max_results: int = 5) -> list[dict]:
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.post(TAVILY_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data.get("results", [])


def _first_valid_email(text: str) -> Optional[str]:
    for match in EMAIL_RE.findall(text or ""):
        domain = match.split("@")[-1].lower()
        if domain not in EMAIL_BLOCKLIST_DOMAINS:
            return match
    return None


async def find_contact_email(business_name: str, city: str, country: str) -> Optional[str]:
    """Best-effort: ask Tavily to search the web for this business and pull an
    email address out of the result snippets. Returns None if nothing usable found."""
    try:
        results = await search(f"{business_name} {city} {country} contact email", max_results=3)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.warning("Tavily email lookup failed for %s: %s", business_name, exc)
        return None

    for result in results:
        email = _first_valid_email(result.get("content", "")) or _first_valid_email(result.get("title", ""))
        if email:
            return email
    return None
