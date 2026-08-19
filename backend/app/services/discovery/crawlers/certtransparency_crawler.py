"""CertTransparency discovery crawler.

Queries Certificate Transparency (CT) logs to find domains and organizations
associated with a given niche in a city/country. CT logs publicly record all
SSL/TLS certificates issued, which often reveal the owning organization's
domain name and location.

See https://crt.sh/ for the public CT search interface.
"""
import asyncio
import logging
import re
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

CT_SEARCH_URL = "https://crt.sh/?q=%s&output=json"


async def _fetch_certtransparency(niche: str, city: str, country: str, session: aiohttp.ClientSession) -> Optional[list[dict]]:
    """Query CertTransparency logs for domains/organizations related to *niche*.

    Returns a list of dicts with keys: domain, organization (if derivable),
    country (from the certificate's subject), and source="certtransparency".
    """
    # crt.sh accepts a domain query; we encode the niche as a rough filter.
    # We'll search for any domain-related entries and then filter locally.
    query = niche.strip().replace(" ", "+")
    url = CT_SEARCH_URL % query

    headers = {"User-Agent": "crawlio/0.1.0 (discovery; +https://crawlio.io)"}
    async with session.get(url, headers=headers) as resp:
        if resp.status != 200:
            logger.warning("CertTransparency returned %s for niche=%s city=%s country=%s", resp.status, niche, city, country)
            return None
        try:
            data = await resp.json()
        except Exception:
            logger.warning("CertTransparency JSON parse failed for niche=%s", niche)
            return None

        results = []
        for entry in data:
            domain = entry.get("domain", "").strip().lower()
            if not domain:
                continue
            # Derive the organization from the name field if available
            name = entry.get("issuer_name", "").strip() or entry.get("common_name", "").strip()
            country_match = entry.get("country", "").strip()

            item = {
                "domain": domain,
                "description": f"CT-log entry for {domain}",
                "category": niche,
                "source": "certtransparency",
            }
            if name:
                item["name"] = name
            if country_match:
                item["country"] = country_match
            results.append(item)

        return results if results else None


async def search_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Search CertTransparency logs for domains/organizations related to *niche* in *city, country*.

    Returns a list of candidate lead dicts. Domains discovered may later be
    resolved via DNS for additional contact info. May return an empty list if
    no CT entries match or the service is unavailable.
    """
    async with aiohttp.ClientSession() as session:
        results = await _fetch_certtransparency(niche, city, country, session)
        if not results:
            return []
        # Deduplicate by domain and apply limit
        seen = set()
        deduped = []
        for item in results:
            d = item.get("domain", "")
            if d and d not in seen:
                seen.add(d)
                deduped.append(item)
        return deduped[:limit]


__all__ = ["search_businesses"]