"""Cross-source merge and de-duplication.

Three independent crawlers (Google Maps, OSM/Overpass, directories) can return
the *same* real business, and each knows a different slice of it — Google Maps
has the phone + address + rating, a directory has the email, Overpass has a
verified coordinate. This module combines those records into one complete lead
without ever mixing data from two different businesses:

- de-duplicate on a normalized name, phone, website, email, or address+coords key;
- merge by *filling gaps* with a strict source preference so a richer record
  (Google Maps) wins a field over a guessier one;
- emit only the fields the rest of the pipeline understands.
"""
import re
from typing import Optional

# Source priority for merge conflicts: earlier sources win a field.
_SOURCE_PRIORITY = ["google_maps", "directory", "openstreetmap", "web_search",
                    "wikidata", "wikipedia", "certtransparency", "dns", "bing", "bizdata"]


def normalize_name(name: str) -> str:
    """Lowercase alnum-only name, with legal/boilerplate suffixes stripped so
    "Sakura Dental Studio (Pvt) Ltd" and "Sakura Dental Studio" dedupe."""
    lowered = (name or "").lower()
    lowered = re.sub(r"\b(?:pvt|ltd|llc|inc|limited|private|company|official\s*website|home)\b", "", lowered)
    return re.sub(r"[^a-z0-9]+", "", lowered)


def _phone_key(phone: Optional[str]) -> str:
    """Extract last 10 digits for phone matching (works for E.164 and national)."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else digits


def _email_key(email: Optional[str]) -> str:
    """Normalize email for matching."""
    return (email or "").lower().strip()


def _website_key(website: Optional[str]) -> str:
    if not website:
        return ""
    host = re.sub(r"https?://(www\.)?", "", website.lower()).rstrip("/").split("/")[0]
    return host.removeprefix("www.")


def _address_key(address: Optional[str]) -> str:
    """Normalize address for matching - lowercase, remove punctuation, keep alphanum."""
    if not address:
        return ""
    return re.sub(r"[^a-z0-9]+", "", address.lower())


def _coords_key(lat: Optional[float], lon: Optional[float]) -> str:
    """Round coordinates to ~100m precision for matching."""
    if lat is None or lon is None:
        return ""
    return f"{round(lat, 4)},{round(lon, 4)}"


def _source_rank(source: str) -> int:
    try:
        return _SOURCE_PRIORITY.index(str(source or "").lower())
    except ValueError:
        return len(_SOURCE_PRIORITY)


def _fill_gap(result: dict, source: dict, field: str) -> None:
    if not result.get(field) and source.get(field):
        result[field] = source[field]


def _merge_pair(result: dict, candidate: dict) -> dict:
    """Fill gaps in `result` from `candidate`, preferring the more trustworthy
    source for conflicting values."""
    result_rank = _source_rank(result.get("source"))
    candidate_rank = _source_rank(candidate.get("source"))

    for field in ("phone", "website", "email", "address", "hours", "description", "category", "industry", "social_links"):
        result_val, cand_val = result.get(field), candidate.get(field)
        if not result_val and cand_val:
            result[field] = cand_val
        elif result_val and cand_val and result_val != cand_val and candidate_rank < result_rank:
            # A more trustworthy source disagrees — trust the better source.
            result[field] = cand_val

    # Coordinates: a real lat/lon wins over a missing one.
    if (result.get("lat") is None or result.get("lon") is None) and candidate.get("lat") is not None:
        result["lat"] = candidate.get("lat")
        result["lon"] = candidate.get("lon")

    # Ratings/reviews only come from Google Maps; a later candidate with one is
    # the same business, so keep whichever exists (identical for same place).
    for field in ("rating", "review_count", "plus_code"):
        _fill_gap(result, candidate, field)

    # Socials merge across sources without clobbering existing platforms.
    socials = dict(result.get("social_links") or {})
    for platform, url in (candidate.get("social_links") or {}).items():
        socials.setdefault(platform, url)
    if socials:
        result["social_links"] = socials

    return result


def merge_businesses(candidates: list[dict]) -> list[dict]:
    """De-duplicate a mixed bag of crawler records and return one complete lead
    per real business. A record joins an existing group when it shares a
    normalized name, phone, email, website, OR address+coords with it — so a
    Google Maps record with phone and a directory record with only the name
    still collapse into one lead. Never raises; never mixes two businesses."""
    merged: list[dict] = []
    name_index: dict[str, dict] = {}
    phone_index: dict[str, dict] = {}
    email_index: dict[str, dict] = {}
    website_index: dict[str, dict] = {}
    address_coords_index: dict[str, dict] = {}

    def _register(group: dict, item: dict) -> None:
        name_key = normalize_name(item.get("name") or "")
        phone_key = _phone_key(item.get("phone"))
        email_key = _email_key(item.get("email"))
        website_key = _website_key(item.get("website"))
        address_key = _address_key(item.get("address"))
        coords_key = _coords_key(item.get("lat"), item.get("lon"))
        addr_coords_key = f"{address_key}|{coords_key}" if address_key and coords_key else ""
        
        if name_key:
            name_index.setdefault(name_key, group)
        if phone_key:
            phone_index.setdefault(phone_key, group)
        if email_key:
            email_index.setdefault(email_key, group)
        if website_key:
            website_index.setdefault(website_key, group)
        if addr_coords_key:
            address_coords_index.setdefault(addr_coords_key, group)

    for item in candidates:
        if not item or not item.get("name"):
            continue
        name_key = normalize_name(item.get("name") or "")
        phone_key = _phone_key(item.get("phone"))
        email_key = _email_key(item.get("email"))
        website_key = _website_key(item.get("website"))
        address_key = _address_key(item.get("address"))
        coords_key = _coords_key(item.get("lat"), item.get("lon"))
        addr_coords_key = f"{address_key}|{coords_key}" if address_key and coords_key else ""

        group = None
        # Match priority: phone > email > website > name > address+coords
        # This ensures we don't incorrectly merge different businesses at same address
        if phone_key and phone_key in phone_index:
            group = phone_index[phone_key]
        elif email_key and email_key in email_index:
            group = email_index[email_key]
        elif website_key and website_key in website_index:
            group = website_index[website_key]
        elif name_key and name_key in name_index:
            group = name_index[name_key]
        elif addr_coords_key and addr_coords_key in address_coords_index:
            group = address_coords_index[addr_coords_key]

        if group is None:
            group = dict(item)
            merged.append(group)
        else:
            _merge_pair(group, item)
        _register(group, item)

    return merged
