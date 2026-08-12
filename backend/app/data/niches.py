import re
from typing import Optional

# Maps a free-text business niche to OpenStreetMap tag filters used to build the
# Overpass query. Each entry is a list of {osm_key: osm_value} filters, OR'd together.
# Niches not found here fall back to a generic name-based search (see discovery_service).
NICHE_TAGS: dict[str, list[dict[str, str]]] = {
    "dental": [{"amenity": "dentist"}],
    "dentist": [{"amenity": "dentist"}],
    "orthodontist": [{"amenity": "dentist"}],
    "plastic surgery": [{"healthcare": "clinic"}, {"amenity": "clinic"}, {"amenity": "doctors"}],
    "plastic surgeon": [{"healthcare": "clinic"}, {"amenity": "clinic"}, {"amenity": "doctors"}],
    "cosmetic surgery": [{"healthcare": "clinic"}, {"amenity": "clinic"}, {"amenity": "doctors"}],
    "cosmetic surgeon": [{"healthcare": "clinic"}, {"amenity": "clinic"}, {"amenity": "doctors"}],
    "aesthetic clinic": [{"healthcare": "clinic"}, {"amenity": "clinic"}],
    "dermatologist": [{"healthcare": "clinic"}, {"amenity": "doctors"}],
    "skin clinic": [{"healthcare": "clinic"}, {"amenity": "doctors"}],
    "restaurant": [{"amenity": "restaurant"}],
    "cafe": [{"amenity": "cafe"}],
    "coffee shop": [{"amenity": "cafe"}],
    "bakery": [{"shop": "bakery"}],
    "hotel": [{"tourism": "hotel"}],
    "gym": [{"leisure": "fitness_centre"}],
    "fitness": [{"leisure": "fitness_centre"}],
    "salon": [{"shop": "hairdresser"}],
    "hair salon": [{"shop": "hairdresser"}],
    "barber": [{"shop": "hairdresser"}],
    "spa": [{"leisure": "spa"}, {"shop": "beauty"}],
    "beauty": [{"shop": "beauty"}],
    "lawyer": [{"office": "lawyer"}],
    "law firm": [{"office": "lawyer"}],
    "attorney": [{"office": "lawyer"}],
    "real estate": [{"office": "estate_agent"}],
    "realtor": [{"office": "estate_agent"}],
    "pharmacy": [{"amenity": "pharmacy"}],
    "clinic": [{"amenity": "clinic"}],
    "doctor": [{"amenity": "doctors"}],
    "hospital": [{"amenity": "hospital"}],
    "veterinary": [{"amenity": "veterinary"}],
    "vet": [{"amenity": "veterinary"}],
    "car dealer": [{"shop": "car"}],
    "auto repair": [{"shop": "car_repair"}],
    "mechanic": [{"shop": "car_repair"}],
    "bank": [{"amenity": "bank"}],
    "school": [{"amenity": "school"}],
    "gas station": [{"amenity": "fuel"}],
    "petrol station": [{"amenity": "fuel"}],
    "supermarket": [{"shop": "supermarket"}],
    "grocery": [{"shop": "supermarket"}],
    "clothing store": [{"shop": "clothes"}],
    "electronics store": [{"shop": "electronics"}],
    "accountant": [{"office": "accountant"}],
    "insurance": [{"office": "insurance"}],
    "photographer": [{"craft": "photographer"}],
    "florist": [{"shop": "florist"}],
    "bar": [{"amenity": "bar"}],
    "pub": [{"amenity": "pub"}],
    "bookstore": [{"shop": "books"}],
    "jewelry": [{"shop": "jewelry"}],
    "travel agency": [{"office": "travel_agent"}],
}


# Curated, human-friendly suggestions shown in the niche field's autocomplete —
# a small, well-mapped subset of NICHE_TAGS' keys rather than every internal key.
SUGGESTED_NICHES: list[str] = [
    "Dental Clinic",
    "Plastic Surgery",
    "Aesthetic Clinic",
    "Real Estate",
    "Restaurant",
    "Cafe",
    "Hotel",
    "Gym",
    "Hair Salon",
    "Spa",
    "Lawyer",
    "Pharmacy",
    "Veterinary",
    "Auto Repair",
    "Photographer",
    "Travel Agency",
]


STOPWORDS = {"a", "an", "the", "and", "or", "shop", "store", "service", "services"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOPWORDS and len(w) > 2}


# Plain-English synonym groups for niches whose OSM tag name alone (e.g.
# "estate_agent") wouldn't help a text-relevance check. Keyed by the same
# canonical NICHE_TAGS name so resolve_niche_tags and niche_keywords agree on
# which niche a query matched.
_NICHE_SYNONYMS: dict[str, list[str]] = {
    "real estate": ["real estate", "property", "estate agent", "realtor"],
    "realtor": ["real estate", "property", "estate agent", "realtor"],
    "dental": ["dental", "dentist"],
    "dentist": ["dental", "dentist"],
    "lawyer": ["lawyer", "law firm", "attorney", "legal"],
    "law firm": ["lawyer", "law firm", "attorney", "legal"],
    "attorney": ["lawyer", "law firm", "attorney", "legal"],
    "auto repair": ["auto repair", "mechanic", "car repair", "workshop"],
    "mechanic": ["auto repair", "mechanic", "car repair", "workshop"],
    "car dealer": ["car dealer", "car showroom", "motors"],
    "gym": ["gym", "fitness"],
    "fitness": ["gym", "fitness"],
    "hair salon": ["salon", "hair salon", "barber"],
    "salon": ["salon", "hair salon", "barber"],
    "barber": ["salon", "hair salon", "barber"],
}


def _match_niche_name(key: str) -> Optional[str]:
    """Find the NICHE_TAGS key a free-text niche resolves to (exact ->
    substring -> word-overlap), or None if nothing matches. Shared by
    resolve_niche_tags, niche_keywords and canonical_niche_key so they all
    agree on which niche a query matched."""
    if not key:
        return None
    if key in NICHE_TAGS:
        return key
    for name in NICHE_TAGS:
        if name in key or key in name:
            return name

    # Loose match: "plastic surgeon" should still hit the "plastic surgery" entry
    # even though neither string is a literal substring of the other. Picks the
    # mapped niche with the most shared significant words (root of surgeon vs
    # surgery already overlaps on "plastic").
    query_words = _words(key)
    best_name, best_overlap = None, 0
    for name in NICHE_TAGS:
        overlap = len(query_words & _words(name))
        if overlap > best_overlap:
            best_name, best_overlap = name, overlap
    return best_name if best_overlap > 0 else None


def niche_keywords(niche: str) -> list[str]:
    """Plain-English keywords for text-relevance matching / search-query
    building, resolved the same way resolve_niche_tags matches a niche
    (exact -> substring -> word-overlap). Returns [] when nothing matches, so
    callers keep their existing raw-string fallback behavior."""
    name = _match_niche_name(niche.strip().lower())
    return _NICHE_SYNONYMS.get(name, [name]) if name else []


def resolve_niche_tags(niche: str) -> tuple[list[dict[str, str]], bool]:
    """Returns (tag filters, is_exact_match). When no mapping is found, callers
    should fall back to a generic name-based search using the raw niche text."""
    name = _match_niche_name(niche.strip().lower())
    if name:
        return NICHE_TAGS[name], True
    return [], False


def _tag_signature(tags: list[dict[str, str]]) -> tuple:
    return tuple(tuple(sorted(d.items())) for d in tags)


# Synonym groups (e.g. "dental"/"dentist", both -> [{"amenity": "dentist"}])
# collapse to whichever NICHE_TAGS key was defined first for that exact tag
# filter, so "Dental Clinic" and "Dentist" canonicalize to the same key.
_CANONICAL_NICHE_NAMES: dict[tuple, str] = {}
for _name, _tags in NICHE_TAGS.items():
    _CANONICAL_NICHE_NAMES.setdefault(_tag_signature(_tags), _name)


def canonical_niche_key(niche: str) -> str:
    """A stable, synonym-collapsed key for a free-text niche — used to share
    one cache entry across differently-phrased but equivalent searches (e.g.
    "Dental Clinic" and "Dentist"). Falls back to normalized free text when
    nothing maps (still stable, just not shared with any synonym)."""
    key = niche.strip().lower()
    name = _match_niche_name(key)
    if name is None:
        return key
    return _CANONICAL_NICHE_NAMES[_tag_signature(NICHE_TAGS[name])]
