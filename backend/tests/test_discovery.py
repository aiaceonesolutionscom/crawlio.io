import pytest

from app.api.v1 import discovery as discovery_api
from app.services import browser_scraper_service, discovery_service, tavily_service, website_scraper_service
from app.workers.tasks_scoring import score_lead_task


@pytest.fixture(autouse=True)
def _no_real_website_scrapes(monkeypatch):
    """Discovery results can carry a website field; without this, the
    free-tier plain-HTTP scraper and Pro's headless-browser scraper would
    both fire real outbound requests at whatever fake domain a test uses."""
    async def fake_extract(url):
        return {}

    async def fake_extract_batch(urls):
        return [{} for _ in urls]

    monkeypatch.setattr(website_scraper_service, "extract_contact_from_website", fake_extract)
    monkeypatch.setattr(browser_scraper_service, "extract_contact_details", fake_extract_batch)


FAKE_RESULTS = [
    {"name": "Bright Smile Dental", "phone": "+92 300 1234567", "email": "hello@brightsmile.pk",
     "website": "https://brightsmile.pk", "address": "Clifton, Karachi", "industry": "Dental",
     "source": "openstreetmap"},
    {"name": "Karachi Dental Studio", "phone": "+92 300 7654321", "email": "hello@kds.pk",
     "website": "https://kds.pk", "address": "DHA, Karachi", "industry": "Dental",
     "source": "openstreetmap"},
]


async def test_discover_returns_results(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async def fake_discover(niche, lat, lon, city, limit=50, radius_m=15000):
        return FAKE_RESULTS

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async with client_factory("user_discover") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "dental", "country": "PK", "city": "Karachi", "lat": 24.86, "lon": 67.01},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["enhanced"] is False  # free plan
    assert body["items"][0]["name"] == "Bright Smile Dental"


async def test_discover_free_tier_drops_incomplete_results(client_factory, monkeypatch):
    """Free tier requires name+website+phone+email+industry on every shown
    lead — anything enrichment can't complete gets dropped, not shown blank."""
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    mixed_results = [
        FAKE_RESULTS[0],  # complete
        {"name": "No Email Clinic", "phone": "+92 300 0000000", "email": None,
         "website": "https://noemail.pk", "address": "Karachi", "industry": "Dental",
         "source": "openstreetmap"},
        {"name": "No Website Clinic", "phone": "+92 300 1111111", "email": "hi@nowebsite.pk",
         "website": None, "address": "Karachi", "industry": "Dental", "source": "openstreetmap"},
    ]

    async def fake_discover(niche, lat, lon, city, limit=50, radius_m=15000):
        return mixed_results

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async with client_factory("user_strict_free") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "dental", "country": "PK", "city": "Karachi", "lat": 24.86, "lon": 67.01},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Bright Smile Dental"


async def test_discover_pro_tier_keeps_incomplete_results(client_factory, monkeypatch):
    """Pro's AI filter is built around two buckets (has-website / no-website),
    so unlike free tier it must NOT drop incomplete leads — it just enriches
    what it can and shows the rest as-is."""
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async def fake_discover(niche, lat, lon, city, limit=50, radius_m=15000):
        return [
            {"name": "No Website Clinic", "phone": "+92 300 1111111", "email": "hi@nowebsite.pk",
             "website": None, "address": "Karachi", "industry": "Dental", "source": "openstreetmap"},
        ]

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async def fake_find_website(*args, **kwargs):
        return None

    monkeypatch.setattr(tavily_service, "find_website_url", fake_find_website)

    async def fake_discover_via_tavily(niche, city, country_name, limit):
        return []

    monkeypatch.setattr(discovery_api, "_discover_via_tavily", fake_discover_via_tavily)

    async with client_factory("user_pro_incomplete") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        ws = (await client.get("/api/v1/workspaces/me")).json()
        await client.patch(f"/api/v1/workspaces/{ws['id']}/plan", json={"plan": "pro"})

        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "dental", "country": "PK", "city": "Karachi", "lat": 24.86, "lon": 67.01},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "No Website Clinic"
    assert body["items"][0]["website"] is None


async def test_discover_pro_tier_merges_tavily_discovered_businesses(client_factory, monkeypatch):
    """Pro+ discovery isn't limited to enriching what OSM found — businesses
    OSM has no record of at all should still show up if Tavily's listing-page
    search + LLM extraction found them, deduped against OSM by name/phone/website."""
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async def fake_discover(niche, lat, lon, city, limit=50, radius_m=15000):
        return [FAKE_RESULTS[0]]  # only one OSM match

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async def fake_find_website(*args, **kwargs):
        return None

    monkeypatch.setattr(tavily_service, "find_website_url", fake_find_website)

    async def fake_discover_via_tavily(niche, city, country_name, limit):
        return [
            {"name": "Smile Studio Karachi", "phone": "+92 300 9999999", "email": None,
             "website": None, "address": "Karachi", "industry": "Dental", "social_links": {},
             "source": "web_search"},
        ]

    monkeypatch.setattr(discovery_api, "_discover_via_tavily", fake_discover_via_tavily)

    async with client_factory("user_pro_web_search") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        ws = (await client.get("/api/v1/workspaces/me")).json()
        await client.patch(f"/api/v1/workspaces/{ws['id']}/plan", json={"plan": "pro"})

        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "dental", "country": "PK", "city": "Karachi", "lat": 24.86, "lon": 67.01},
        )

    assert resp.status_code == 200
    body = resp.json()
    names = {item["name"] for item in body["items"]}
    assert names == {"Bright Smile Dental", "Smile Studio Karachi"}


async def test_discover_free_tier_never_calls_tavily_discovery(client_factory, monkeypatch):
    """Tavily-backed discovery is a paid-tier feature — free tier must not
    trigger it at all, regardless of how incomplete the OSM results are."""
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async def fake_discover(niche, lat, lon, city, limit=50, radius_m=15000):
        return FAKE_RESULTS

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async def unexpected_call(*args, **kwargs):
        raise AssertionError("_discover_via_tavily must not run on free tier")

    monkeypatch.setattr(discovery_api, "_discover_via_tavily", unexpected_call)

    async with client_factory("user_free_no_tavily_discovery") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "dental", "country": "PK", "city": "Karachi", "lat": 24.86, "lon": 67.01},
        )

    assert resp.status_code == 200


async def test_discover_unavailable_returns_503(client_factory, monkeypatch):
    async def failing_discover(niche, lat, lon, city, limit=50, radius_m=15000):
        raise discovery_service.DiscoveryUnavailableError("OpenStreetMap search is temporarily unavailable")

    monkeypatch.setattr(discovery_service, "discover_businesses", failing_discover)

    async with client_factory("user_discover_fail") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "dental", "country": "PK", "city": "Karachi", "lat": 24.86, "lon": 67.01},
        )

    assert resp.status_code == 503


async def test_discover_import_creates_leads_and_skips_duplicates(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_import") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})

        first_import = await client.post(
            "/api/v1/leads/discover/import",
            json={"items": FAKE_RESULTS},
        )
        second_import = await client.post(
            "/api/v1/leads/discover/import",
            json={"items": [FAKE_RESULTS[1]]},  # same email as before -> duplicate
        )

    assert first_import.status_code == 200
    first_body = first_import.json()
    assert len(first_body["created"]) == 2
    assert first_body["skipped"] == []

    second_body = second_import.json()
    assert len(second_body["created"]) == 0
    assert second_body["skipped"][0]["reason"] == "duplicate"


async def test_discover_import_respects_daily_limit(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)
    monkeypatch.setitem(discovery_api.DAILY_DISCOVERY_IMPORT_LIMITS, "free", 2)

    items = [
        {"name": f"Business {i}", "phone": None, "email": f"biz{i}@example.com",
         "website": None, "address": None, "source": "openstreetmap"}
        for i in range(4)
    ]

    async with client_factory("user_daily_limit") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.post("/api/v1/leads/discover/import", json={"items": items})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["created"]) == 2
    assert len(body["skipped"]) == 2
    assert all(s["reason"] == "daily_limit_reached" for s in body["skipped"])


async def test_discover_reports_remaining_today(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)
    monkeypatch.setitem(discovery_api.DAILY_DISCOVERY_IMPORT_LIMITS, "free", 5)

    async def fake_discover(niche, lat, lon, city, limit=50, radius_m=15000):
        return FAKE_RESULTS

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async with client_factory("user_remaining") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.post("/api/v1/leads/discover/import", json={"items": FAKE_RESULTS})  # 2 leads added

        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "dental", "country": "PK", "city": "Karachi", "lat": 24.86, "lon": 67.01},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["daily_limit"] == 5
    assert body["remaining_today"] == 3
