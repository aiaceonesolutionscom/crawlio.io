"""RDAP discovery crawler.

Queries RDAP (Registration Domain Access Protocol) servers for domain
registration/organization data. RDAP is the modern replacement for WHOIS and
provides structured JSON data about domain registrants, including
organization name, contact details, and location.

See https://rdap.online/en/ and https://tools.ietf.org/html/rfc7483 .
"""
import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Well-known RDAP bootstrap endpoints for common TLDs, plus a fallback to
# rely on the domain's own zone RDAP server.
_WELL_KNOWN_BOOTSTRAP = {
    ".com": "https://rdap.verisign.com/rdap/",
    ".org": "https://publicinterestregistry.org/rdap/",
    ".net": "https://rdap.verisign.com/rdap/",
    ".io": "https://rdap.afilias.io/rdap/",
    ".co": "https://rdap.nic.co/rdap/",
    ".pk": "https://rdap.pkregistry.org/rdap/",
}


async def _fetch_rdap(domain: str, session: aiohttp.ClientSession) -> Optional[dict]:
    """Fetch RDAP data for a single *domain*.

    Returns the parsed RDAP JSON response, or None on failure.
    """
    # Determine the TLD to pick a well-known bootstrap server, otherwise
    # construct a generic RDAP query.
    tld = domain.split(".")[-1].lower()
    bootstrap = _WELL_KNOWN_BOOTSTRAP.get(tld)

    base_url = bootstrap or "https://rdap.org/rdap/"

    query_url = f"{base_url}?domain={domain}&email=%&poc=%&spon=%"

    headers = {
        "Accept": "application/rdap+json",
        "User-Agent": "crawlio/0.1.0 (discovery; +https://crawlio.io)",
    }
    async with session.get(query_url, headers=headers) as resp:
        if resp.status != 200:
            logger.warning("RDAP returned %s for domain=%s", resp.status, domain)
            return None
        try:
            return await resp.json()
        except Exception:
            logger.warning("RDAP JSON parse failed for domain=%s", domain)
            return None


async def search_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Search RDAP for domain registration data related to *niche*.

    This method tries well-known bootstrap RDAP servers for domains that may
    be associated with businesses in the given niche/location. It returns
    parsed registrant/organization data that can be used as lead candidates.

    Note: RDAP lookups are best-effort; many domains have privacy-protected
    registrant data, so results can be sparse.
    """
    # We don't have a specific domain to query; instead, we'll attempt a
    # best-effort search by trying common business-related domains.
    # In practice, this crawler is most effective when called with a known
    # domain (e.g. from a prior Maps/OSM scrape). Here we return an empty
    # list to indicate the method requires a domain focus.
    # 
    # TODO: When integrated, each lead's website domain could be queried
    # individually via _fetch_rdap().
    return []


__all__ = ["search_businesses"]