"""Wikidata discovery crawler.

Queries Wikidata (Wikipedia's sister database) for entities matching a given
niche (e.g. "restaurant", "clinic") in a given city/country. Uses the Wikidata
JSON API with SPARQL filters to find items matching the niche and location.

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
    Uses string concatenation to avoid f-string brace/escaping issues.
    """
    niche_lower = niche.lower()
    # Build query parts using concatenation for safety
    parts = [
        "SELECT ?item ?itemLabel ?itemDescription ?coordinates ?website ",
        "WHERE {",
        "  SERVICE wikibase:mw {",
        "    bd:serviceParam wikibase:language \"en\". ",
        # Filter by label containing the niche (case-insensitive)
        "    FILTER regex(?itemLabel, \"" + niche_lower + "\", \"i\") ",
        "  }",
        "  OPTIONAL { ?item wdt:P31 ?type . }",
        "  OPTIONAL { ?item wdt:P625 ?coordinates . }",
        "  OPTIONAL { ?item wdt:P856 ?website . }",
        "  SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". }",
        "}",
        "LIMIT 50",
    ]
    return "".join(parts)


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
        try:
            data = await resp.json()
        except Exception:
            logger.warning("Wikidata JSON parse failed for niche=%s", niche)
            return None
        results = []
        for binding in data.get("results", {}).get("bindings", []):
            item = {}
            # Safely get item ID from the Wikidata URI
            item_val = binding.get("item", {}).get("value", "")
            if item_val:
                item["id"] = item_val.rsplit("/", 1)[-1]
            else:
                item["id"] = ""

            # Safely get label
            label_val = binding.get("itemLabel", {}).get("value", "")
            if label_val:
                item["name"] = label_val
            else:
                item["name"] = ""

            # Safely get description
            desc_val = binding.get("itemDescription", {}).get("value", "")
            if desc_val:
                item["description"] = desc_val[:200]  # truncate
            else:
                item["description"] = ""

            # Safely get coordinates
            item["lat"] = None
            item["lon"] = None
            coords_val = binding.get("coordinates", {}).get("value", "")
            if coords_val:
                try:
                    # Handle Wikibase coordinate format: POINT(lat lon) or internal format
                    if "T" in coords_val:
                        lat_lon = coords_val.split("T")[1].split("^")
                        item["lat"] = float(lat_lon[0])
                        item["lon"] = float(lat_lon[1])
                    else:
                        # Try POINT format: split by space after POINT(
                        if "POINT(" in coords_val:
                            coords_clean = coords_val.replace("POINT(", "").replace(")", "")
                            parts = coords_clean.split()
                            if len(parts) >= 2:
                                item["lat"] = float(parts[0])
                                item["lon"] = float(parts[1])
                except Exception:
                    pass

            # Safely get website
            web_val = binding.get("website", {}).get("value", "")
            if web_val:
                item["website"] = web_val
            else:
                item["website"] = ""

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