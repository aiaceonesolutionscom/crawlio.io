import respx
from httpx import Response

from app.services import geocoding_service, overpass_service

_ELEMENT = {
    "tags": {
        "name": "Sakura Dental Studio",
        "addr:housenumber": "12",
        "addr:street": "Khayaban-e-Shahbaz",
        "phone": "+92 21 111 222 333",
        "website": "https://sakura.pk",
        "contact:facebook": "https://facebook.com/sakuradental",
    },
    "center": {"lat": 24.86, "lon": 67.01},
}


def test_parse_elements_extracts_structured_fields():
    results = overpass_service._parse_elements([_ELEMENT], "Karachi", "Dental Clinic")
    assert len(results) == 1
    item = results[0]
    assert item["name"] == "Sakura Dental Studio"
    assert item["address"] == "12, Khayaban-e-Shahbaz, Karachi"
    assert item["phone"] == "+92 21 111 222 333"
    assert item["website"] == "https://sakura.pk"
    assert item["social_links"] == {"facebook": "https://facebook.com/sakuradental"}
    assert item["lat"] == 24.86
    assert item["lon"] == 67.01
    assert item["source"] == "openstreetmap"


def test_parse_elements_drops_non_latin_name_with_no_english_fallback():
    element = {"tags": {"name": "کراچی ڈینٹل", "phone": "+92 21 111 222 333"}, "center": {"lat": 1, "lon": 2}}
    assert overpass_service._parse_elements([element], "Karachi", "Dental Clinic") == []


def test_parse_elements_prefers_english_name_tag():
    element = {
        "tags": {"name": "کراچی ڈینٹل", "name:en": "Karachi Dental", "phone": "+92 21 111 222 333"},
        "center": {"lat": 1, "lon": 2},
    }
    results = overpass_service._parse_elements([element], "Karachi", "Dental Clinic")
    assert results[0]["name"] == "Karachi Dental"


def test_parse_elements_drops_name_only_result_with_no_contact_signal():
    element = {"tags": {"name": "Mystery Business"}, "center": {"lat": 1, "lon": 2}}
    assert overpass_service._parse_elements([element], "Karachi", "Dental Clinic") == []


async def test_run_overpass_query_returns_empty_list_when_all_mirrors_fail():
    with respx.mock:
        for mirror in overpass_service.OVERPASS_MIRRORS:
            respx.post(mirror).mock(return_value=Response(500))
        result = await overpass_service._run_overpass_query("[out:json]; out;")

    assert result == []


async def test_run_overpass_query_returns_first_successful_mirror():
    with respx.mock:
        for mirror in overpass_service.OVERPASS_MIRRORS[:-1]:
            respx.post(mirror).mock(return_value=Response(500))
        respx.post(overpass_service.OVERPASS_MIRRORS[-1]).mock(
            return_value=Response(200, json={"elements": [_ELEMENT]})
        )
        result = await overpass_service._run_overpass_query("[out:json]; out;")

    assert result == [_ELEMENT]


async def test_discover_businesses_returns_empty_when_geocoding_fails(monkeypatch):
    async def fake_geocode(query):
        return None

    monkeypatch.setattr(geocoding_service, "geocode", fake_geocode)

    result = await overpass_service.discover_businesses("Dental Clinic", "Nowhereville", "Testland")
    assert result == []


async def test_discover_businesses_uses_fallback_query_for_unmapped_niche(monkeypatch):
    async def fake_geocode(query):
        return {"lat": 24.86, "lon": 67.01, "display_name": "Karachi"}

    captured_queries = []

    async def fake_run_query(query):
        captured_queries.append(query)
        return [_ELEMENT] if 'name"~"Escape Room"' in query else []

    monkeypatch.setattr(geocoding_service, "geocode", fake_geocode)
    monkeypatch.setattr(overpass_service, "_run_overpass_query", fake_run_query)

    result = await overpass_service.discover_businesses("Escape Room", "Karachi", "Pakistan", limit=5)

    assert len(result) == 1
    assert any('name"~"Escape Room"' in q for q in captured_queries)


async def test_discover_businesses_returns_mapped_niche_results(monkeypatch):
    async def fake_geocode(query):
        return {"lat": 24.86, "lon": 67.01, "display_name": "Karachi"}

    async def fake_run_query(query):
        return [_ELEMENT]

    monkeypatch.setattr(geocoding_service, "geocode", fake_geocode)
    monkeypatch.setattr(overpass_service, "_run_overpass_query", fake_run_query)

    result = await overpass_service.discover_businesses("Dental Clinic", "Karachi", "Pakistan", limit=5)

    assert len(result) == 1
    assert result[0]["name"] == "Sakura Dental Studio"
