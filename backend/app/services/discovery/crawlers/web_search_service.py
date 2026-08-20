"""Tavily web search — an opt-in, last-resort top-up source.

Google Maps + OSM/Overpass + free directories are the primary sources; this
module only runs when discovery_service finds their combined, validated
result count still short of what was requested (thinner markets outside the
biggest cities). It is capped to one bounded call per search.

Design constraint, load-bearing: this module returns **name + website only**,
never a guessed email/phone/address. The old Tavily-based pipeline's bad data
didn't come from Tavily itself (it only ever returned URLs and text
snippets) — it came from an LLM step downstream that read raw snippet text
and guessed contact fields out of it, with no deliverability check. That
step doesn't exist here: real contact info for anything this module finds
comes from enrichment_pipeline.py's actual website scrape + MX-verified
email, exactly like every other source. A directory/portal URL is filtered
out before it ever becomes a candidate (contact_extraction.is_own_website),
and the business name goes through the same SEO-spam cleanup as Google Maps
listings.

Never raises — any failure (missing/bad key, rate limit, timeout, no
results) returns [] so a search never breaks because this optional source is
unavailable.

MULTI-QUERY STRATEGY: Runs multiple targeted queries to maximize coverage:
1. Official website query
2. Google Maps place query (finds GBP links)
3. Contact info query (phone/email)
4. Review/best-of query
"""
import asyncio
import logging

import httpx

from app.core.config import settings
from app.services.discovery.contact_extraction import clean_business_name, is_own_website

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
TIMEOUT = 12.0

# Multi-query templates for maximum coverage
TAVILY_QUERIES = [
    "{niche} {city} {country} official website",
    "{niche} {city} {country} google maps place",
    "{niche} {city} {country} phone email contact",
    "best {niche} {city} {country} reviews",
    "{niche} {city} {country} linkedin company",
]


async def _tavily_search(client: httpx.AsyncClient, query: str, max_results: int) -> list[dict]:
    """Execute a single Tavily search query."""
    try:
        resp = await client.post(
            TAVILY_URL,
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Tavily query failed: %s", exc)
        return []


async def find_extra_businesses(niche: str, city: str, country: str, limit: int) -> list[dict]:
    """Return up to `limit` extra {name, website, source, industry} candidates
    from multiple targeted web searches. Never sets email/phone/address."""
    if not settings.tavily_enabled or not settings.tavily_api_key or limit < 1:
        return []

    max_results_per_query = max(1, min(limit, settings.tavily_max_results))
    all_records: list[dict] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Run all queries concurrently for speed
        query_tasks = [
            _tavily_search(client, q.format(niche=niche, city=city, country=country), max_results_per_query)
            for q in TAVILY_QUERIES
        ]
        all_results = await asyncio.gather(*query_tasks, return_exceptions=True)

        for results in all_results:
            if isinstance(results, Exception):
                logger.warning("Tavily query error: %s", results)
                continue
            
            for result in results:
                url = (result.get("url") or "").strip()
                title = (result.get("title") or "").strip()
                if not url or not title:
                    continue
                if url in seen_urls:
                    continue
                if not is_own_website(url):
                    # Directory/portal/marketplace domain — never surface it as if it
                    # were a business's own site.
                    continue
                name = clean_business_name(title)
                if not name:
                    continue
                seen_urls.add(url)
                all_records.append({
                    "name": name,
                    "website": url,
                    "source": "web_search",
                    "industry": niche.strip().title(),
                    "social_links": {},
                })
                if len(all_records) >= limit:
                    break
            
            if len(all_records) >= limit:
                break

    return all_records[:limit]
