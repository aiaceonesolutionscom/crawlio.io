"""Tests for the Sprint 3 worldwide-source crawlers and fill ladder.

Pure unit tests (no network): BizData JSON parsing + category mapping, Bing Maps
JSON-LD parsing + listing-card fallback, niche-synonym expansion, and the
country-wide top-cities fallback helper.
"""
import json

from app.services.crawlers import bing_maps_crawler, bizdata_crawler, niche_synonyms
from app.services.geo_service import top_cities


# ---------------------------------------------------------------------------
# BizData
# ---------------------------------------------------------------------------

def test_bizdata_category_map():
    assert bizdata_crawler._category_for("Dental Clinic") == "dentist"
    assert bizdata_crawler._category_for("Best Restaurants") == "restaurant"
    assert bizdata_crawler._category_for("boutique") is None


def test_bizdata_parse_businesses():
    payload = {
        "total": 2,
        "businesses": [
            {
                "name": "Café de Flore",
                "category": "cafe",
                "address": "172 Boulevard Saint-Germain, Paris",
                "phone": "+33 1 45 48 55 26",
                "website": "https://cafedeflore.fr",
                "email": "contact@cafedeflore.fr",
                "lat": 48.8540,
                "lon": 2.3325,
            },
            {"name": ""},
            {"not_a_business": True},
        ],
    }
    records = bizdata_crawler._parse_businesses(payload)
    assert len(records) == 1
    r = records[0]
    assert r["name"] == "Café de Flore"
    assert r["source"] == "bizdata"
    assert r["email"] == "contact@cafedeflore.fr"
    assert r["lat"] == 48.8540


def test_bizdata_parse_alt_latlon_names():
    payload = {"businesses": [{"name": "X", "latitude": 1.0, "longitude": 2.0}]}
    records = bizdata_crawler._parse_businesses(payload)
    assert records[0]["lat"] == 1.0
    assert records[0]["lon"] == 2.0


# ---------------------------------------------------------------------------
# Bing Maps
# ---------------------------------------------------------------------------

def test_bing_jsonld_local_business():
    html = f"""
    <html><head>
    <script type="application/ld+json">{json.dumps({
        "@type": "LocalBusiness",
        "name": "The Coffee House",
        "telephone": "+44 20 7946 0000",
        "url": "https://www.thecoffeehouse.co.uk",
        "address": {
            "streetAddress": "123 Oxford Street",
            "addressLocality": "London",
            "addressRegion": "London",
            "postalCode": "W1D 1BS",
            "addressCountry": "GB",
        },
        "geo": {"latitude": 51.5074, "longitude": -0.1278},
        "aggregateRating": {"ratingValue": 4.5, "reviewCount": 1234},
    })}</script>
    </head></html>
    """
    records = bing_maps_crawler._extract_json_ld(html)
    assert len(records) == 1
    r = records[0]
    assert r["name"] == "The Coffee House"
    assert r["phone"] == "+44 20 7946 0000"
    assert r["website"] == "https://www.thecoffeehouse.co.uk"
    assert "123 Oxford Street" in r["address"]
    assert r["lat"] == 51.5074
    assert r["source"] == "bing_maps"


def test_bing_jsonld_graph_and_filter():
    html = f"""
    <script type="application/ld+json">{json.dumps({"@graph": [
        {"@type": "WebSite", "name": "Search Engine", "url": "https://x.com"},
        {"@type": "Restaurant", "name": "Pizza Roma", "telephone": "+39 06 1234 5678"},
        {"@type": "Thing", "name": "Random Place"},
    ]})}</script>
    """
    records = bing_maps_crawler._extract_json_ld(html)
    names = {r["name"] for r in records}
    assert "Pizza Roma" in names
    assert "Search Engine" not in names
    assert "Random Place" not in names


def test_bing_listing_card_fallback():
    html = """
    <li class="b_entityTitle listing">
      <div>Doe Plumbing | 555-0100 | 12 Main St</div>
    </li>
    <li class="listing">
      <div>Smith Dental | 555-0199</div>
    </li>
    """
    records = bing_maps_crawler._extract_listing_cards(html)
    names = {r["name"] for r in records}
    assert "Doe Plumbing" in names
    assert "Smith Dental" in names
    assert all(r.get("phone") for r in records)


def test_bing_record_rejects_non_http_website():
    item = {"name": "X", "url": "javascript:void(0)", "telephone": "+1 555 0100"}
    record = bing_maps_crawler._record_from_jsonld(item)
    assert record["website"] is None
    assert record["name"] == "X"


# ---------------------------------------------------------------------------
# Niche synonyms
# ---------------------------------------------------------------------------

def test_expand_synonyms_returns_original_first():
    terms = niche_synonyms.expand_synonyms("dentist")
    assert terms[0] == "dentist"
    assert "dental clinic" in terms


def test_expand_synonyms_dedupes():
    terms = niche_synonyms.expand_synonyms("dental clinic")
    assert len(terms) == len(set(terms))


def test_expand_synonyms_unknown_niche():
    terms = niche_synonyms.expand_synonyms("quantum tofu studio")
    assert terms == ["quantum tofu studio"]


def test_expand_synonyms_empty():
    assert niche_synonyms.expand_synonyms("") == []


def test_canonical_category():
    assert niche_synonyms.canonical_category("dentist") == "dentist"
    assert niche_synonyms.canonical_category("unknown thing") == ""


# ---------------------------------------------------------------------------
# Fill ladder helper
# ---------------------------------------------------------------------------

def test_top_cities_returns_first_n():
    cities = top_cities("PK", n=2)
    assert len(cities) == 2
    assert cities[0]["name"] == "Lahore"


def test_top_cities_unknown_country():
    assert top_cities("ZZ", n=2) == []
