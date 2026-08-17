from app.api.v1 import discovery as discovery_api
from app.services.discovery import discovery_service
from app.services.enrichment import enrichment_jobs


async def _store_job_locally(search_id, items, meta):
    enrichment_jobs._MEM_JOBS[search_id] = {
        "search_id": search_id, "status": "in_progress", "meta": meta, "items": items,
    }
    return True


async def _get_job_locally(search_id):
    return enrichment_jobs._MEM_JOBS.get(search_id)


async def _save_job_locally(search_id, job):
    enrichment_jobs._MEM_JOBS[search_id] = job


async def _noop_enrich(*a, **k):
    return None


async def _poll_items(client, search_id, timeout=5.0):
    """Discovery is backgrounded now — poll the job store (what the status
    endpoint serves) until the crawl finished AND the shared cache write has
    been committed in step 3. The HTTP response's `already_in_workspace` is a
    schema default, so we inspect the stored job's items, not the body."""
    import asyncio
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = enrichment_jobs._MEM_JOBS.get(search_id)
        items = (job or {}).get("items") or []
        if items and all("already_in_workspace" in it for it in items):
            resp = await client.get(f"/api/v1/leads/discover/{search_id}")
            return resp.json()
        await asyncio.sleep(0.05)
    resp = await client.get(f"/api/v1/leads/discover/{search_id}")
    return resp.json()


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

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)
    monkeypatch.setattr(discovery_api, "_enrich_batch_async", _noop_enrich)
    monkeypatch.setattr(enrichment_jobs, "create_enrichment_job", _store_job_locally)
    monkeypatch.setattr(enrichment_jobs, "get_enrichment_job", _get_job_locally)
    monkeypatch.setattr(enrichment_jobs, "save_job", _save_job_locally)

    async with client_factory("user_cache_test") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})

        # First search is backgrounded: returns a search_id immediately, then the
        # poll surfaces the freshly crawled (non-cached) lead.
        resp1 = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )
        assert resp1.status_code == 200
        body1 = resp1.json()
        assert body1["items"] == []
        assert body1["search_id"] is not None
        body1 = await _poll_items(client, body1["search_id"])
        assert len(body1["items"]) == 1
        assert body1["items"][0]["cache_hit"] is False
        assert body1["items"][0]["name"] == "Acme Dental"

        # Second search is served straight from the shared cache.
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

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)
    monkeypatch.setattr(discovery_api, "_enrich_batch_async", _noop_enrich)
    monkeypatch.setattr(enrichment_jobs, "create_enrichment_job", _store_job_locally)
    monkeypatch.setattr(enrichment_jobs, "get_enrichment_job", _get_job_locally)
    monkeypatch.setattr(enrichment_jobs, "save_job", _save_job_locally)

    async with client_factory("user_cache_synonym_test") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})

        resp1 = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )
        await _poll_items(client, resp1.json()["search_id"])
        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dentist", "country": "PK", "city": "Karachi", "limit": 1},
        )

    assert resp.status_code == 200
    assert resp.json()["items"][0]["cache_hit"] is True
    assert call_count["n"] == 1
