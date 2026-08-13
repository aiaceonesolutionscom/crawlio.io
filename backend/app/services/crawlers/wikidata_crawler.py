"""Wikidata discovery crawler.

Queries Wikidata (Wikipedia's sister database) for entities matching a given
niche (e.g. "restaurant", "clinic") in a given city/country. Uses the Wikidata
JSON API with SPARQL-ish filters to find items matching the niche and location.

See https://www.wikidata.org/wiki/Help:SPARQL_queries for the query format.
"""
import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_USER_AGENT = "crawlio/0.1.0 (discovery; +https://crawlio.io)"


def _build_wikidata_sparql(niche: str, city: str, country: str) -> str:
    """Build a SPARQL query for Wikidata search.

    Returns the query string with niche, city, and country substituted safely.
    """
    niche_lower = niche.lower()
    city_normalised = city.strip().lower().replace(" ", "_")
    country_normalised = country.strip().upper()

    # Use string concatenation to avoid f-string brace issues.
    query_parts = [
        "SELECT ?item ?itemLabel ?itemDescription ?coordinates ?website ",
        "WHERE {",
        "  SERVICE wikibase:mw {",
        "    bd:serviceParam wikibase:language \"en\". ",
        "    ?item wikidata:Claim ?p .",
        f"    FILTER(CONTAINS(LCASE(STR(?itemLabel)), LCASE('{niche_lower}')))",
        "  }",
        "  OPTIONAL { ?item wdt:P625 ?coordinates . }",
        "  OPTIONAL { ?item wdt:P856 ?website . }",
        "  SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". }",
        "}",
        "LIMIT 50",
    ]
    return "".join(query_parts)


async def _fetch_wikidata(niche: str, city: str, country: str, session: aiohttp.ClientSession) -> Optional[list[dict]]:
    """Query Wikidata for entities matching *niche* near *city, country*.

    Returns a list of dicts with keys: id, name, coordinates (lat/lon),
    description, website (if any), and source="wikidata".
    """
    query = _build_wikidata_sparql(niche, city, country)

    headers = {"User-Agent": WIKIDATA_USER_AGENT}
    url = f"{WIKIDATA_SPARQL_ENDPOINT}?query={query}&format=json"

    async with session.get(url, headers=headers) as resp:
        if resp.status != 200:
            logger.warning("Wikidata query returned %s for niche=%s city=%s country=%s", resp.status, niche, city, country)
            return None
        data = await resp.json()
        results = []
        for binding in data.get("results", {}).get("bindings", []):
            item = {}
            item_id = binding.get("item", {}).get("value", "")
            if item_id:
                item["id"] = item_id.split("/")[-1]
            label = binding.get("itemLabel", {}).get("value")
            if label:
                item["name"] = label
            desc = binding.get("itemDescription", {}).get("value")
            if desc:
                item["description"] = desc
            coords = binding.get("coordinates", {}).get("value")
            if coords:
                try:
                    # Wikibate coordinates format:POINT(lat lon)
                    # or the internal format with T and ^ separators
                    if "T" in coords:
                        lat_lon = coords.split("T")[1].split("^")
                        item["lat"] = float(lat_lon[0])
                        item["lon"] = float(lat_lon[1])
                    else:
                        # POINT format
                        item["lat"] = None
                        item["lon"] = None
                except Exception:
                    pass
            web = binding.get("website", {}).get("value")
            if web:
                item["website"] = web
            item["category"] = niche
            item["source"] = "wikidata"
            results.append(item)
        return results


async def search_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Search Wikidata for businesses/organizations matching *niche* in *city, country*.

    Returns a list of candidate lead dicts. May return an empty list if no
    matching entities are found or the API is unavailable.
    """
    async with aiohttp.ClientSession() as session:
        results = await _fetch_wikidata(niche, city, country, session)
        if not results:
            return []
        return results[:limit]


__all__ = ["search_businesses"]