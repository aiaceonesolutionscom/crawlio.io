import respx
from httpx import Response

from app.services.discovery import geocoding_service


async def test_geocode_returns_lat_lon_and_display_name():
    mock_response = [
        {"lat": "24.8607343", "lon": "67.0011364", "display_name": "Karachi, Sindh, Pakistan"},
    ]
    with respx.mock:
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=Response(200, json=mock_response)
        )
        result = await geocoding_service.geocode("Karachi, Pakistan unique-query-1")

    assert result == {"lat": 24.8607343, "lon": 67.0011364, "display_name": "Karachi, Sindh, Pakistan"}


async def test_geocode_requests_english_results():
    """Nominatim localizes display_name into the region's own language by
    default (e.g. Urdu for a Pakistani location) unless English is requested
    explicitly — every other field in a lead is English, so this must always
    be set."""
    mock_response = [{"lat": "1.0", "lon": "2.0", "display_name": "Test City"}]
    with respx.mock:
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=Response(200, json=mock_response)
        )
        await geocoding_service.geocode("Karachi, Pakistan unique-query-lang")

    assert route.calls[0].request.url.params["accept-language"] == "en"


async def test_geocode_returns_none_when_nothing_found():
    with respx.mock:
        respx.get("https://nominatim.openstreetmap.org/search").mock(return_value=Response(200, json=[]))
        result = await geocoding_service.geocode("Nowhereville-unique-query-2")

    assert result is None


async def test_geocode_returns_none_on_http_failure():
    with respx.mock:
        respx.get("https://nominatim.openstreetmap.org/search").mock(return_value=Response(500))
        result = await geocoding_service.geocode("Some City-unique-query-3")

    assert result is None


async def test_geocode_caches_repeated_queries():
    """A second call for the same (normalized) query must not hit Nominatim
    again — this is required by Nominatim's usage policy as much as it is a
    performance optimization."""
    mock_response = [{"lat": "1.0", "lon": "2.0", "display_name": "Cached City"}]
    with respx.mock:
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=Response(200, json=mock_response)
        )
        await geocoding_service.geocode("Cache Test City-unique-query-4")
        await geocoding_service.geocode("  CACHE TEST CITY-unique-query-4  ")

    assert route.call_count == 1


async def test_geocode_business_prefers_real_address_over_city():
    mock_response = [{"lat": "5.0", "lon": "6.0", "display_name": "123 Real St, Testville"}]
    with respx.mock:
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=Response(200, json=mock_response)
        )
        result = await geocoding_service.geocode_business(
            "123 Real St-unique-query-5", "Testville-unique-query-5", "Testland-unique-query-5"
        )

    assert result == {"lat": 5.0, "lon": 6.0, "display_name": "123 Real St, Testville"}
    assert "123 Real St-unique-query-5" in route.calls[0].request.url.params["q"]


async def test_geocode_business_falls_back_to_city_when_address_is_just_the_city():
    mock_response = [{"lat": "7.0", "lon": "8.0", "display_name": "Cityonly, Testland"}]
    with respx.mock:
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=Response(200, json=mock_response)
        )
        result = await geocoding_service.geocode_business(
            "Cityonly-unique-query-6", "Cityonly-unique-query-6", "Testland-unique-query-6"
        )

    assert result == {"lat": 7.0, "lon": 8.0, "display_name": "Cityonly, Testland"}
    # Only the city+country candidate should have been tried, since address == city.
    assert route.calls[0].request.url.params["q"] == "Cityonly-unique-query-6, Testland-unique-query-6"


# --- Nominatim POI search (the second OSM discovery surface) -------------------


async def test_search_places_parses_poi_with_contact_details():
    mock_response = [
        {
            "name": "Smile Dental Clinic",
            "lat": "24.86",
            "lon": "67.0",
            "extratags": {
                "contact:phone": "0300 1234567",
                "contact:website": "https://smiledental.pk",
                "contact:email": "info@smiledental.pk",
                "contact:facebook": "https://facebook.com/smiledental",
            },
            "address": {"house_number": "12", "road": "Main Blvd"},
        }
    ]
    with respx.mock:
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=Response(200, json=mock_response)
        )
        result = await geocoding_service.search_places("Dental Clinic", "Karachi-unique-query-7", "Pakistan")

    assert len(result) == 1
    rec = result[0]
    assert rec["name"] == "Smile Dental Clinic"
    assert rec["phone"] == "0300 1234567"
    assert rec["website"] == "https://smiledental.pk"
    assert rec["email"] == "info@smiledental.pk"
    assert rec["address"] == "12, Main Blvd, Karachi-unique-query-7"
    assert rec["social_links"] == {"facebook": "https://facebook.com/smiledental"}
    assert rec["lat"] == 24.86
    assert rec["lon"] == 67.0
    assert rec["source"] == "nominatim"


async def test_search_places_requests_extratags_and_english():
    """Contact fields (phone/website/email/socials) only come back from the
    OSM extratags, and display names must stay English — both must be requested."""
    mock_response = [{"name": "X", "lat": "1.0", "lon": "2.0", "extratags": {}}]
    with respx.mock:
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=Response(200, json=mock_response)
        )
        await geocoding_service.search_places("Dental Clinic", "Lhr-unique-query-8", "Pakistan")

    params = route.calls[0].request.url.params
    assert params["extratags"] == "1"
    assert params["addressdetails"] == "1"
    assert params["accept-language"] == "en"
    assert params["q"] == "Dental Clinic in Lhr-unique-query-8, Pakistan"


async def test_search_places_returns_empty_on_http_failure():
    with respx.mock:
        respx.get("https://nominatim.openstreetmap.org/search").mock(return_value=Response(500))
        result = await geocoding_service.search_places("Dental Clinic", "Karachi-unique-query-9", "Pakistan")

    assert result == []


async def test_search_places_caches_repeated_queries():
    mock_response = [{"name": "Cached Clinic", "lat": "1.0", "lon": "2.0", "extratags": {}}]
    with respx.mock:
        route = respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=Response(200, json=mock_response)
        )
        await geocoding_service.search_places("Dental Clinic", "Cacheville-unique-query-10", "Pakistan")
        await geocoding_service.search_places("   dental    clinic ", "Cacheville-unique-query-10", "Pakistan")

    assert route.call_count == 1


async def test_search_places_skips_records_without_name_or_coords():
    mock_response = [
        {"name": "", "lat": "1.0", "lon": "2.0", "extratags": {}},
        {"name": "No Coords", "extratags": {}},
        {"name": "Valid", "lat": "3.0", "lon": "4.0", "extratags": {}},
    ]
    with respx.mock:
        respx.get("https://nominatim.openstreetmap.org/search").mock(
            return_value=Response(200, json=mock_response)
        )
        result = await geocoding_service.search_places("Dental Clinic", "Testville-unique-query-11", "Pakistan")

    assert len(result) == 1
    assert result[0]["name"] == "Valid"
