"""Wikipedia discovery crawler.

Queries Wikipedia (via the MediaWiki API) for articles matching a given niche
in a given city/country. Returns article titles that are about organizations,
businesses, or places relevant to the niche.

See https://www.mediawiki.org/wiki/Extension:API#Param_search for the search
format.
"""
import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

WIKIPEDIA_API_ENDPOINT = "https://en.wikipedia.org/w/api.php"


async def _fetch_wikipedia(niche: str, city: str, country: str, session: aiohttp.ClientSession) -> Optional[list[dict]]:
    """Query Wikipedia for articles matching *niche* near *city, country*.

    Returns a list of dicts with keys: id (title), name, description/extract,
    and source="wikipedia".
    """
    # Search for the niche combined with city/country
    search_query = f"{niche} {city} {country}".strip()

    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": search_query,
        "srlimit": 20,
    }

    headers = {"User-Agent": "crawlio/0.1.0 (discovery; +https://crawlio.io)"}
    async with session.get(WIKIPEDIA_API_ENDPOINT, params=params, headers=headers) as resp:
        if resp.status != 200:
            logger.warning("Wikipedia API returned %s for niche=%s city=%s country=%s", resp.status, niche, city, country)
            return None
        data = await resp.json()
        results = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title")
            if not title:
                continue
            # Fetch the extract/summary for the article
            extract_params = {
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "explaintext": True,
                "titles": title,
            }
            async with session.get(WIKIPEDIA_API_ENDPOINT, params=extract_params, headers=headers) as resp2:
                if resp2.status != 200:
                    continue
                extract_data = await resp2.json()
                pages = extract_data.get("query", {}).get("pages", {})
                for page in pages.values():
                    extract = page.get("extract")
                    if not extract:
                        continue
                    results.append({
                        "id": title,
                        "name": title,
                        "description": extract[:500],  # truncate
                        "category": niche,
                        "source": "wikipedia",
                    })
            if len(results) >= 20:
                break
        return results


async def search_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Search Wikipedia for articles about businesses/organizations matching *niche* in *city, country*.

    Returns a list of candidate lead dicts. May return an empty list if no
    matching articles are found or the API is unavailable.
    """
    async with aiohttp.ClientSession() as session:
        results = await _fetch_wikipedia(niche, city, country, session)
        if not results:
            return []
        return results[:limit]


__all__ = ["search_businesses"]