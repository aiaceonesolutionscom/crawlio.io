import asyncio
import time

from app.api.v1 import discovery as discovery_api
from app.services.discovery import discovery_service
from app.services.enrichment import enrichment_jobs
from app.workers.tasks_scoring import score_lead_task


async def _store_job_locally(search_id, items, meta):
    enrichment_jobs._MEM_JOBS[search_id] = {
        "search_id": search_id, "status": "in_progress", "meta": meta, "items": items,
    }
    return True


async def _get_job_locally(search_id):
    return enrichment_jobs._MEM_JOBS.get(search_id)


async def _save_job_locally(search_id, job):
    enrichment_jobs._MEM_JOBS[search_id] = job


async def _poll_items(client, search_id, timeout=5.0):
    """Discovery is now backgrounded — poll the job store (what the status
    endpoint serves) until the crawl finishes AND the already_in_workspace
    annotation has been applied in step 3 (set right after the cache write,
    before enrichment). The HTTP response always carries the schema default
    `already_in_workspace: False`, so we inspect the stored job, not the body."""
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


def _monkeypatch_discovery(monkeypatch, items):
    async def fake_discover(niche, city, country, country_code="PK", limit=50, enrich_candidates=False, source_counts=None):
        return list(items)

    async def noop_enrich(*a, **k):
        return None

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)
    monkeypatch.setattr(discovery_api, "_enrich_batch_async", noop_enrich)
    monkeypatch.setattr(enrichment_jobs, "create_enrichment_job", _store_job_locally)
    monkeypatch.setattr(enrichment_jobs, "get_enrichment_job", _get_job_locally)
    monkeypatch.setattr(enrichment_jobs, "save_job", _save_job_locally)
    # POST /leads dispatches scoring through Celery; there's no broker here.
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)


async def test_already_imported_lead_is_flagged_on_fresh_search(client_factory, monkeypatch):
    _monkeypatch_discovery(monkeypatch, [
        {"name": "Acme Dental", "phone": "+923001234567", "email": "info@acme.pk", "source": "google_maps", "social_links": {}, "lat": 24.8, "lon": 67.0},
        {"name": "New Clinic", "phone": "+923009999999", "email": "hi@newclinic.pk", "source": "google_maps", "social_links": {}, "lat": 24.8, "lon": 67.0},
    ])

    async with client_factory("user_already_imported") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        # Already have Acme Dental in the CRM (e.g. imported yesterday).
        await client.post("/api/v1/leads", json={"name": "Acme Dental", "email": "info@acme.pk"})

        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 2},
        )
        assert resp.status_code == 200
        body = await _poll_items(client, resp.json()["search_id"])

    assert body["status"] != "failed"
    items = {i["name"]: i for i in body["items"]}
    assert items["Acme Dental"]["already_in_workspace"] is True
    assert items["New Clinic"]["already_in_workspace"] is False


async def test_already_imported_flag_matches_by_phone_too(client_factory, monkeypatch):
    _monkeypatch_discovery(monkeypatch, [
        {"name": "Acme Dental", "phone": "+923001234567", "email": None, "source": "google_maps", "social_links": {}, "lat": 24.8, "lon": 67.0},
    ])

    async with client_factory("user_already_imported_phone") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.post("/api/v1/leads", json={"name": "Acme Dental (dup)", "phone": "+923001234567"})

        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )
        body = await _poll_items(client, resp.json()["search_id"])

    assert body["items"][0]["already_in_workspace"] is True


async def test_already_imported_flag_is_workspace_scoped(client_factory, monkeypatch):
    """A lead imported by Workspace X must not mark the same business as
    already-in-CRM for Workspace Y — the shared cache is global, but the
    already_in_workspace annotation must not leak across workspaces."""
    _monkeypatch_discovery(monkeypatch, [
        {"name": "Acme Dental", "phone": "+923001234567", "email": "info@acme.pk", "source": "google_maps", "social_links": {}, "lat": 24.8, "lon": 67.0},
    ])

    async with client_factory("user_ws_x") as client_x:
        await client_x.post("/api/v1/workspaces", json={"name": "Workspace X"})
        await client_x.post("/api/v1/leads", json={"name": "Acme Dental", "email": "info@acme.pk"})

    async with client_factory("user_ws_y") as client_y:
        await client_y.post("/api/v1/workspaces", json={"name": "Workspace Y"})
        resp = await client_y.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )
        body = await _poll_items(client_y, resp.json()["search_id"])

    assert body["items"][0]["already_in_workspace"] is False


async def test_already_imported_flag_applied_on_cache_hit_too(client_factory, monkeypatch):
    _monkeypatch_discovery(monkeypatch, [
        {"name": "Acme Dental", "phone": "+923001234567", "email": "info@acme.pk", "source": "google_maps", "social_links": {}, "lat": 24.8, "lon": 67.0},
    ])

    async with client_factory("user_cache_flag_1") as client_a:
        await client_a.post("/api/v1/workspaces", json={"name": "A"})
        # Warm the shared cache from workspace A's search.
        resp_a = await client_a.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )
        await _poll_items(client_a, resp_a.json()["search_id"])

    async with client_factory("user_cache_flag_2") as client_b:
        await client_b.post("/api/v1/workspaces", json={"name": "B"})
        await client_b.post("/api/v1/leads", json={"name": "Acme Dental", "email": "info@acme.pk"})

        resp = await client_b.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )

    body = resp.json()
    assert body["items"][0]["cache_hit"] is True
    assert body["items"][0]["already_in_workspace"] is True
