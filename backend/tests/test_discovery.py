import pytest

from app.services import discovery_service
from app.services.discovery_service import DiscoveryUnavailableError


@pytest.mark.asyncio
async def test_orchestrates_all_sources_and_merges(monkeypatch):
    async def fake_maps(*args, **kwargs):
        return [{"name": "Sakura Dental Studio", "phone": "0300 1234567", "address": "Karachi", "source": "google_maps"}]

    async def fake_osm(*args, **kwargs):
        return [{"name": "Sakura Dental Studio", "lat": 24.86, "lon": 67.0, "source": "openstreetmap"}]

    async def fake_dir(*args, **kwargs):
        return [{"name": "Sakura Dental Studio", "phone": "03001234567", "email": "info@sakura.pk", "source": "directory"}]

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fake_maps)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", fake_osm)
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", fake_dir)
    # No DNS in tests — treat every domain as deliverable.
    monkeypatch.setattr(discovery_service.lead_validator.settings, "validate_emails", False)

    leads = await discovery_service.discover_businesses("Dental Clinic", "Karachi", "Pakistan", country_code="PK", limit=5)

    assert len(leads) == 1
    lead = leads[0]
    assert lead["name"] == "Sakura Dental Studio"
    assert lead["phone"] == "+923001234567"
    assert lead["email"] == "info@sakura.pk"
    assert lead["lat"] == 24.86
    assert lead["lon"] == 67.0
    assert lead["completeness"] > 0


@pytest.mark.asyncio
async def test_drops_leads_without_contact_channel(monkeypatch):
    async def fake_maps(*args, **kwargs):
        return [{"name": "Ghost Business", "source": "google_maps"}]

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fake_maps)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", lambda *a, **k: __import__("asyncio").sleep(0) or [])
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", lambda *a, **k: __import__("asyncio").sleep(0) or [])

    leads = await discovery_service.discover_businesses("Dental Clinic", "Karachi", "Pakistan", country_code="PK", limit=5)
    assert leads == []


@pytest.mark.asyncio
async def test_strips_directory_website_but_keeps_phone(monkeypatch):
    async def fake_maps(*args, **kwargs):
        return [{"name": "Acme", "phone": "03001234567", "website": "https://www.yellowpages.com.pk/acme", "source": "google_maps"}]

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fake_maps)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", lambda *a, **k: __import__("asyncio").sleep(0) or [])
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", lambda *a, **k: __import__("asyncio").sleep(0) or [])

    leads = await discovery_service.discover_businesses("Dental Clinic", "Karachi", "Pakistan", country_code="PK", limit=5)
    assert len(leads) == 1
    assert leads[0]["website"] is None
    assert leads[0]["phone"] == "+923001234567"


@pytest.mark.asyncio
async def test_tavily_not_called_when_structured_sources_meet_limit(monkeypatch):
    async def fake_maps(*args, **kwargs):
        return [{"name": "Acme", "phone": "03001234567", "source": "google_maps"}]

    async def fake_empty(*args, **kwargs):
        return []

    called = False

    async def fake_tavily(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fake_maps)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.web_search_service, "find_extra_businesses", fake_tavily)
    monkeypatch.setattr(discovery_service.settings, "tavily_enabled", True)
    monkeypatch.setattr(discovery_service.settings, "tavily_api_key", "test-key")

    leads = await discovery_service.discover_businesses("Dental Clinic", "Karachi", "Pakistan", country_code="PK", limit=1)

    assert len(leads) == 1
    assert called is False


@pytest.mark.asyncio
async def test_tavily_tops_up_when_structured_sources_fall_short(monkeypatch):
    async def fake_maps(*args, **kwargs):
        return [{"name": "Acme", "phone": "03001234567", "source": "google_maps"}]

    async def fake_empty(*args, **kwargs):
        return []

    calls = []

    async def fake_tavily(niche, city, country, limit):
        calls.append(limit)
        return [{"name": "New Clinic", "website": "https://newclinic.pk", "source": "web_search", "industry": "Dental Clinic", "social_links": {}}]

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fake_maps)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.web_search_service, "find_extra_businesses", fake_tavily)
    monkeypatch.setattr(discovery_service.settings, "tavily_enabled", True)
    monkeypatch.setattr(discovery_service.settings, "tavily_api_key", "test-key")

    leads = await discovery_service.discover_businesses("Dental Clinic", "Islamabad", "Pakistan", country_code="PK", limit=5)

    assert calls == [4]  # asked for exactly the remaining gap (5 - 1), not the full limit
    names = {lead["name"] for lead in leads}
    assert names == {"Acme", "New Clinic"}
    new_clinic = next(lead for lead in leads if lead["name"] == "New Clinic")
    assert new_clinic["website"] == "https://newclinic.pk"
    assert new_clinic.get("email") is None
    assert new_clinic.get("phone") is None


@pytest.mark.asyncio
async def test_tavily_never_called_when_disabled_by_default(monkeypatch):
    async def fake_empty(*args, **kwargs):
        return []

    async def fake_dir(*args, **kwargs):
        return [{"name": "X", "phone": "03001234567", "source": "directory"}]

    called = False

    async def fake_tavily(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", fake_dir)
    monkeypatch.setattr(discovery_service.web_search_service, "find_extra_businesses", fake_tavily)
    # tavily_enabled defaults to False — not touched here.

    leads = await discovery_service.discover_businesses("Dental Clinic", "Islamabad", "Pakistan", country_code="PK", limit=20)
    assert len(leads) == 1
    assert called is False


@pytest.mark.asyncio
async def test_nearby_city_fallback_tags_results_and_merges(monkeypatch):
    async def fake_maps(niche, city, country, limit):
        # Nearby-city fallback intentionally skips Maps (the slow part) — only
        # ever called for the primary city.
        assert city == "Islamabad"
        return [{"name": "Isb Dental", "phone": "03001234567", "source": "google_maps"}]

    async def fake_empty(*args, **kwargs):
        return []

    async def fake_osm(niche, city, country, limit):
        if city == "Rawalpindi":
            return [{"name": "Pindi Dental", "phone": "03009999999", "source": "openstreetmap"}]
        return []

    def fake_nearby(country_code, city_name, n=2):
        assert city_name == "Islamabad"
        return [{"name": "Rawalpindi", "lat": 33.6, "lon": 73.0}]

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fake_maps)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", fake_osm)
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.geo_service, "nearby_cities", fake_nearby)

    leads = await discovery_service.discover_businesses("Dental Clinic", "Islamabad", "Pakistan", country_code="PK", limit=5)

    names = {lead["name"]: lead for lead in leads}
    assert set(names) == {"Isb Dental", "Pindi Dental"}
    assert names["Isb Dental"]["result_city"] == "Islamabad"
    assert names["Isb Dental"]["is_fallback_city"] is False
    assert names["Pindi Dental"]["result_city"] == "Rawalpindi"
    assert names["Pindi Dental"]["is_fallback_city"] is True


async def test_nearby_city_fallback_never_calls_maps(monkeypatch):
    """The whole point of skipping Maps for fallback cities is speed — assert
    it structurally, not just via the data that happens to come back."""
    maps_calls = []

    async def fake_maps(niche, city, country, limit):
        maps_calls.append(city)
        return [{"name": "Isb Dental", "phone": "03001234567", "source": "google_maps"}] if city == "Islamabad" else []

    async def fake_empty(*args, **kwargs):
        return []

    def fake_nearby(country_code, city_name, n=2):
        return [{"name": "Rawalpindi", "lat": 33.6, "lon": 73.0}, {"name": "Taxila", "lat": 33.7, "lon": 72.8}]

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fake_maps)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.geo_service, "nearby_cities", fake_nearby)

    await discovery_service.discover_businesses("Dental Clinic", "Islamabad", "Pakistan", country_code="PK", limit=20)

    assert maps_calls == ["Islamabad"]


@pytest.mark.asyncio
async def test_nearby_city_fallback_not_used_when_primary_meets_limit(monkeypatch):
    async def fake_maps(*args, **kwargs):
        return [{"name": "Acme", "phone": "03001234567", "source": "google_maps"}]

    async def fake_empty(*args, **kwargs):
        return []

    called = False

    def fake_nearby(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fake_maps)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.geo_service, "nearby_cities", fake_nearby)

    leads = await discovery_service.discover_businesses("Dental Clinic", "Karachi", "Pakistan", country_code="PK", limit=1)

    assert len(leads) == 1
    assert called is False


@pytest.mark.asyncio
async def test_nearby_city_fallback_no_candidates_available(monkeypatch):
    async def fake_maps(*args, **kwargs):
        return [{"name": "Acme", "phone": "03001234567", "source": "google_maps"}]

    async def fake_empty(*args, **kwargs):
        return []

    def fake_nearby(*args, **kwargs):
        return []  # e.g. a country with only one known city

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fake_maps)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", fake_empty)
    monkeypatch.setattr(discovery_service.geo_service, "nearby_cities", fake_nearby)

    leads = await discovery_service.discover_businesses("Dental Clinic", "SoloCity", "Testland", country_code="XX", limit=5)

    assert len(leads) == 1
    assert leads[0]["name"] == "Acme"


@pytest.mark.asyncio
async def test_raises_when_all_sources_down(monkeypatch):
    async def fail(*args, **kwargs):
        raise RuntimeError("source down")

    monkeypatch.setattr(discovery_service.maps_crawler, "search_businesses", fail)
    monkeypatch.setattr(discovery_service.overpass_service, "discover_businesses", fail)
    monkeypatch.setattr(discovery_service.directory_scraper, "search_businesses", fail)

    with pytest.raises(DiscoveryUnavailableError):
        await discovery_service.discover_businesses("Dental Clinic", "Karachi", "Pakistan", country_code="PK", limit=5)
