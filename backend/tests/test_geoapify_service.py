import respx
from httpx import Response

from app.services.discovery import geoapify_service
from app.services.discovery.geoapify_service import GEOAPIFY_URL


def _feature():
    return {
        "type": "Feature",
        "properties": {
            "name": "Smile Dental Studio",
            "lat": 24.86,
            "lon": 67.01,
            "address_line1": "Shop 4, Main Blvd",
            "address_line2": "Karachi",
            "datasource": {
                "raw": {
                    "contact:phone": "0300 1234567",
                    "contact:website": "https://smiledental.pk",
                    "contact:email": "info@smiledental.pk",
                    "contact:instagram": "https://instagram.com/smiledental",
                }
            },
            "opening_hours": {"weekday_text": ["Mon: 9am-6pm", "Sat: 9am-1pm"]},
        },
        "geometry": {"coordinates": [67.01, 24.86]},
    }


async def test_search_businesses_returns_empty_without_api_key(monkeypatch):
    """No key configured -> [] and, crucially, no HTTP call at all."""
    monkeypatch.setattr(geoapify_service, "api_key", lambda name: "")
    result = await geoapify_service.search_businesses("Dental Clinic", "Karachi", "PK")
    assert result == []


async def test_search_businesses_sends_key_categories_and_circle(monkeypatch):
    monkeypatch.setattr(geoapify_service, "api_key", lambda name: "test-key")
    with respx.mock:
        route = respx.get(GEOAPIFY_URL).mock(return_value=Response(200, json={"features": []}))
        await geoapify_service.search_businesses("Dental Clinic", "Karachi", "PK", limit=10)

    params = route.calls[0].request.url.params
    assert params["apiKey"] == "test-key"
    assert params["lang"] == "en"
    assert params["categories"] == "healthcare.dentist"
    assert params["filter"] == "circle:67.01,24.86,20000"
    assert params["bias"] == "proximity:67.01,24.86"
    assert "text" not in params


async def test_search_businesses_skips_unmapped_niche(monkeypatch):
    monkeypatch.setattr(geoapify_service, "api_key", lambda name: "test-key")
    with respx.mock:
        route = respx.get(GEOAPIFY_URL).mock(return_value=Response(200, json={"features": []}))
        result = await geoapify_service.search_businesses("Widget Manufacturing", "Karachi", "PK", limit=10)

    assert result == []
    assert not route.calls


async def test_search_businesses_parses_feature_and_contact_details(monkeypatch):
    monkeypatch.setattr(geoapify_service, "api_key", lambda name: "test-key")
    with respx.mock:
        respx.get(GEOAPIFY_URL).mock(return_value=Response(200, json={"features": [_feature()]}))
        result = await geoapify_service.search_businesses("Dental Clinic", "Karachi", "PK", limit=10)

    assert len(result) == 1
    rec = result[0]
    assert rec["name"] == "Smile Dental Studio"
    assert rec["phone"] == "0300 1234567"
    assert rec["website"] == "https://smiledental.pk"
    assert rec["email"] == "info@smiledental.pk"
    assert rec["address"] == "Shop 4, Main Blvd, Karachi"
    assert rec["social_links"] == {"instagram": "https://instagram.com/smiledental"}
    assert rec["hours"] == "Mon: 9am-6pm; Sat: 9am-1pm"
    assert rec["lat"] == 24.86
    assert rec["lon"] == 67.01
    assert rec["industry"] == "Dental Clinic"
    assert rec["source"] == "geoapify"


async def test_search_businesses_returns_empty_on_http_failure(monkeypatch):
    monkeypatch.setattr(geoapify_service, "api_key", lambda name: "test-key")
    with respx.mock:
        respx.get(GEOAPIFY_URL).mock(return_value=Response(500))
        result = await geoapify_service.search_businesses("Dental Clinic", "Karachi", "PK")

    assert result == []


async def test_search_businesses_skips_features_without_name(monkeypatch):
    monkeypatch.setattr(geoapify_service, "api_key", lambda name: "test-key")
    nameless = _feature()
    nameless["properties"].pop("name")
    with respx.mock:
        respx.get(GEOAPIFY_URL).mock(return_value=Response(200, json={"features": [nameless]}))
        result = await geoapify_service.search_businesses("Dental Clinic", "Karachi", "PK")

    assert result == []


async def test_search_businesses_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(geoapify_service, "api_key", lambda name: "test-key")
    monkeypatch.setattr(geoapify_service.settings, "geoapify_enabled", False)
    result = await geoapify_service.search_businesses("Dental Clinic", "Karachi", "PK")

    assert result == []
