import pytest

from app.api.v1 import discovery as discovery_api
from app.services import (
    browser_scraper_service,
    discovery_service,
    duckduckgo_service,
    enrichment_jobs,
    listing_extraction_service,
    tavily_service,
    website_scraper_service,
)
from app.workers.tasks_enrichment import enrich_discovered_batch
from app.workers.tasks_scoring import score_lead_task


@pytest.fixture(autouse=True)
def _no_real_website_scrapes(monkeypatch):
    """Discovery results can carry a website field; without this, the
    free-tier plain-HTTP scraper and Pro's headless-browser scraper would
    both fire real outbound requests at whatever fake domain a test uses."""
    async def fake_extract(url, country_code=None):
        return {}

    async def fake_extract_batch(urls, country_code=None):
        return [{} for _ in urls]

    monkeypatch.setattr(website_scraper_service, "extract_contact_from_website", fake_extract)
    monkeypatch.setattr(browser_scraper_service, "extract_contact_details", fake_extract_batch)

    # Enrichment is background work; in tests we stub the job store + dispatch so
    # no Redis/Celery/Playwright calls happen and the POST returns immediately.
    async def fake_create_job(search_id, items, meta):
        return True

    monkeypatch.setattr(enrichment_jobs, "create_enrichment_job", fake_create_job)
    monkeypatch.setattr(enrich_discovered_batch, "delay", lambda *args, **kwargs: None)


# ---------------------------------------------------------------------------
# discovery_service (Phase 1 URL finder) unit tests
# ---------------------------------------------------------------------------

DENTAL_WEBSITE_RESULT = {
    "title": "Sakura Dental Studio – Dental Clinic in Karachi | Official Website",
    "url": "https://sakura.pk",
    "content": "Book an appointment at our Karachi dental clinic today.",
}
SECOND_DENTAL_WEBSITE_RESULT = {
    "title": "Bright Smile Clinic | Best Dental Clinic in Karachi",
    "url": "https://brightsmile.pk",
    "content": "Dental clinic in Karachi offering crowns and whitening.",
}


async def test_discover_businesses_keeps_direct_websites_only(monkeypatch):
    social = {"title": "Sakura Dental Studio - Facebook", "url": "https://www.facebook.com/sakura", "content": ""}
    directory = {"title": "Sakura Dental Studio on Yelp", "url": "https://www.yelp.com/biz/sakura", "content": ""}
    off_topic = {
        "title": "Sakura Blossom Sushi Recipe Blog",
        "url": "https://recipeblog.example/sakura",
        "content": "A sakura dessert from Osaka.",
    }
    async def fake_duck(query, max_results=8):
        return [DENTAL_WEBSITE_RESULT, social, directory, off_topic]

    async def fake_tavily(query, max_results=5):
        return []

    monkeypatch.setattr(duckduckgo_service, "search", fake_duck)
    monkeypatch.setattr(tavily_service, "search", fake_tavily)
    monkeypatch.setattr(tavily_service, "discover_listing_pages", lambda *a, **k: [])

    found = await discovery_service.discover_businesses("dental clinic", "Karachi", "Pakistan", limit=10)

    assert len(found) == 1
    assert found[0]["name"] == "Sakura Dental Studio"
    assert found[0]["website"] == "https://sakura.pk"
    assert found[0]["source"] == "web_search"


async def test_discover_businesses_dedupes_and_caps_at_limit(monkeypatch):
    dupe_title = "Sakura Dental Studio - Karachi"
    async def fake_duck(query, max_results=8):
        return [DENTAL_WEBSITE_RESULT, {**DENTAL_WEBSITE_RESULT, "title": dupe_title}]

    async def fake_tavily(query, max_results=5):
        return [SECOND_DENTAL_WEBSITE_RESULT]

    async def fake_listing_pages(*args, **kwargs):
        return []

    monkeypatch.setattr(duckduckgo_service, "search", fake_duck)
    monkeypatch.setattr(tavily_service, "search", fake_tavily)
    monkeypatch.setattr(tavily_service, "discover_listing_pages", fake_listing_pages)

    found = await discovery_service.discover_businesses("dental clinic", "Karachi", "Pakistan", limit=1)

    assert len(found) == 1


async def test_discover_businesses_extracts_website_less_from_directories(monkeypatch):
    """Businesses without their own website still surface via directory/listicle
    pages (Tavily raw content + AI extraction) — real leads, not mock data."""
    async def no_direct(*args, **kwargs):
        return []

    async def listing_pages(*args, **kwargs):
        return [{"title": "Best dental clinics Karachi", "url": "https://best.pk/dental",
                 "raw_content": "x" * 600}]

    async def extract(niche, city, raw_content, max_items=15):
        return [
            {"name": "Smile Studio Karachi", "phone": "+92 300 9999999", "email": None,
             "website": None, "address": "DHA, Karachi"},
            {"name": "White Pearl Dental", "phone": "+92 300 8888888", "email": "hi@whitepearl.pk",
             "website": None, "address": "Clifton, Karachi"},
        ]

    monkeypatch.setattr(tavily_service, "search", no_direct)
    monkeypatch.setattr(duckduckgo_service, "search", no_direct)
    monkeypatch.setattr(tavily_service, "discover_listing_pages", listing_pages)
    monkeypatch.setattr(listing_extraction_service, "extract_businesses", extract)

    found = await discovery_service.discover_businesses("dental clinic", "Karachi", "Pakistan", limit=10)

    names = {item["name"] for item in found}
    assert names == {"Smile Studio Karachi", "White Pearl Dental"}
    assert all(item["source"] == "web_search" for item in found)


async def test_discover_businesses_raises_when_every_provider_fails(monkeypatch):
    async def failing(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(tavily_service, "search", failing)
    monkeypatch.setattr(duckduckgo_service, "search", failing)

    with pytest.raises(discovery_service.DiscoveryUnavailableError):
        await discovery_service.discover_businesses("dental clinic", "Karachi", "Pakistan", limit=10)


# ---------------------------------------------------------------------------
# Discovery API tests
# ---------------------------------------------------------------------------

FAKE_RESULTS = [
    {"name": "Bright Smile Dental", "phone": "+92 300 1234567", "email": "hello@brightsmile.pk",
     "website": "https://brightsmile.pk", "address": "Clifton, Karachi", "industry": "Dental",
     "source": "web_search"},
    {"name": "Karachi Dental Studio", "phone": "+92 300 7654321", "email": "hello@kds.pk",
     "website": "https://kds.pk", "address": "DHA, Karachi", "industry": "Dental",
     "source": "web_search"},
]

DISCOVER_PAYLOAD = {"niche": "dental", "country": "PK", "city": "Karachi", "lat": 24.86, "lon": 67.01}


async def test_discover_returns_results(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async def fake_discover(niche, city, country, limit=50):
        return FAKE_RESULTS

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async with client_factory("user_discover") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.post("/api/v1/leads/discover", json=DISCOVER_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["enhanced"] is False  # free plan
    assert body["items"][0]["name"] == "Bright Smile Dental"


async def test_discover_free_tier_keeps_incomplete_results(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    mixed_results = [
        FAKE_RESULTS[0],  # complete
        {"name": "No Email Clinic", "phone": "+92 300 0000000", "email": None,
         "website": "https://noemail.pk", "address": "Karachi", "industry": "Dental",
         "source": "web_search"},
        {"name": "No Website Clinic", "phone": "+92 300 1111111", "email": "hi@nowebsite.pk",
         "website": None, "address": "Karachi", "industry": "Dental", "source": "web_search"},
    ]

    async def fake_discover(niche, city, country, limit=50):
        return mixed_results

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async with client_factory("user_free_incomplete") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.post("/api/v1/leads/discover", json=DISCOVER_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["search_id"] is not None
    names = {item["name"] for item in body["items"]}
    assert names == {"Bright Smile Dental", "No Email Clinic", "No Website Clinic"}


async def test_discover_status_returns_enrichment_progress(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async def fake_discover(niche, city, country, limit=50):
        return FAKE_RESULTS

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async with client_factory("user_status") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        ws = (await client.get("/api/v1/workspaces/me")).json()

        # Wrong workspace -> job must be hidden.
        async def fake_get_job_other(search_id):
            return {
                "search_id": search_id,
                "status": "in_progress",
                "meta": {"workspace_id": "someone-elses-workspace"},
                "items": [FAKE_RESULTS[0]],
            }

        monkeypatch.setattr(enrichment_jobs, "get_enrichment_job", fake_get_job_other)
        wrong_ws = await client.get("/api/v1/leads/discover/abc-def")
        assert wrong_ws.status_code == 404

        # Own workspace -> enrichment progress returned.
        async def fake_get_job_own(search_id):
            return {
                "search_id": search_id,
                "status": "in_progress",
                "meta": {"workspace_id": ws["id"]},
                "items": [
                    {**FAKE_RESULTS[0], "enrichment_status": "done", "completeness": 100},
                    {**FAKE_RESULTS[1], "enrichment_status": "enriching"},
                ],
            }

        monkeypatch.setattr(enrichment_jobs, "get_enrichment_job", fake_get_job_own)
        resp = await client.get("/api/v1/leads/discover/abc-def")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["items"][0]["enrichment_status"] == "done"
    assert body["items"][0]["completeness"] == 100


async def test_discover_pro_tier_keeps_incomplete_results(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async def fake_discover(niche, city, country, limit=50):
        return [
            {"name": "No Website Clinic", "phone": "+92 300 1111111", "email": "hi@nowebsite.pk",
             "website": None, "address": "Karachi", "industry": "Dental", "source": "web_search"},
        ]

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async with client_factory("user_pro_incomplete") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        ws = (await client.get("/api/v1/workspaces/me")).json()
        await client.patch(f"/api/v1/workspaces/{ws['id']}/plan", json={"plan": "pro"})

        resp = await client.post("/api/v1/leads/discover", json=DISCOVER_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "No Website Clinic"
    assert body["items"][0]["website"] is None


async def test_discover_unavailable_returns_503(client_factory, monkeypatch):
    async def failing_discover(niche, city, country, limit=50):
        raise discovery_service.DiscoveryUnavailableError("Web search is temporarily unavailable")

    monkeypatch.setattr(discovery_service, "discover_businesses", failing_discover)

    async with client_factory("user_discover_fail") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.post("/api/v1/leads/discover", json=DISCOVER_PAYLOAD)

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
         "website": None, "address": None, "source": "web_search"}
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

    async def fake_discover(niche, city, country, limit=50):
        return FAKE_RESULTS

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    async with client_factory("user_remaining") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.post("/api/v1/leads/discover/import", json={"items": FAKE_RESULTS})  # 2 leads added

        resp = await client.post("/api/v1/leads/discover", json=DISCOVER_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["daily_limit"] == 5
    assert body["remaining_today"] == 3