import respx
from httpx import Response

from app.services import geocoding_service


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
