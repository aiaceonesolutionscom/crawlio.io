import re

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


def resolve_niche_tags(niche: str) -> tuple[list[dict[str, str]], bool]:
    """Returns (tag filters, is_exact_match). When no mapping is found, callers
    should fall back to a generic name-based search using the raw niche text."""
    key = niche.strip().lower()
    if key in NICHE_TAGS:
        return NICHE_TAGS[key], True
    for name, tags in NICHE_TAGS.items():
        if name in key or key in name:
            return tags, True

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
    if best_name and best_overlap > 0:
        return NICHE_TAGS[best_name], True

    return [], False
