from app.services.discovery import discovery_service
from app.services.enrichment import enrichment_jobs


async def test_discover_endpoint_caches_and_reuses_across_requests(client_factory, monkeypatch):
    call_count = {"n": 0}

    async def fake_discover(niche, city, country, country_code="PK", limit=50, enrich_candidates=False, source_counts=None):
        call_count["n"] += 1
        return [{
            "name": "Acme Dental",
            "phone": "+923001234567",
            "email": None,
            "website": None,
            "address": "Karachi",
            "lat": 24.8,
            "lon": 67.0,
            "industry": "Dental Clinic",
            "social_links": {},
            "source": "google_maps",
            "completeness": 50,
        }]

    async def fake_job_store_unavailable(*a, **k):
        # Forces the deterministic inline-enrichment fallback path instead of
        # a real Celery dispatch, which this test environment has no worker for.
        return False

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)
    monkeypatch.setattr(enrichment_jobs, "create_enrichment_job", fake_job_store_unavailable)

    async with client_factory("user_cache_test") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})

        resp1 = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )
        assert resp1.status_code == 200
        body1 = resp1.json()
        assert len(body1["items"]) == 1
        assert body1["items"][0]["cache_hit"] is False
        assert body1["items"][0]["name"] == "Acme Dental"

        resp2 = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert len(body2["items"]) == 1
        assert body2["items"][0]["cache_hit"] is True
        assert body2["items"][0]["name"] == "Acme Dental"

    # The live discovery pipeline only ran once — the second request was
    # served entirely from the shared cache.
    assert call_count["n"] == 1


async def test_discover_endpoint_niche_synonym_reuses_same_cache(client_factory, monkeypatch):
    call_count = {"n": 0}

    async def fake_discover(niche, city, country, country_code="PK", limit=50, enrich_candidates=False, source_counts=None):
        call_count["n"] += 1
        return [{
            "name": "Acme Dental", "phone": "+923001234567", "email": None, "website": None,
            "address": "Karachi", "lat": 24.8, "lon": 67.0, "industry": "Dental Clinic",
            "social_links": {}, "source": "google_maps", "completeness": 50,
        }]

    async def fake_job_store_unavailable(*a, **k):
        return False

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)
    monkeypatch.setattr(enrichment_jobs, "create_enrichment_job", fake_job_store_unavailable)

    async with client_factory("user_cache_synonym_test") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})

        await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )
        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dentist", "country": "PK", "city": "Karachi", "limit": 1},
        )

    assert resp.status_code == 200
    assert resp.json()["items"][0]["cache_hit"] is True
    assert call_count["n"] == 1
