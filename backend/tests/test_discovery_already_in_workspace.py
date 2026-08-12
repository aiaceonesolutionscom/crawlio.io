from app.services import discovery_service, enrichment_jobs, enrichment_pipeline
from app.workers.tasks_scoring import score_lead_task


def _fake_job_store_unavailable():
    async def _f(*a, **k):
        return False
    return _f


async def test_already_imported_lead_is_flagged_on_fresh_search(client_factory, monkeypatch):
    async def fake_discover(niche, city, country, country_code="PK", limit=50):
        return [
            {"name": "Acme Dental", "phone": "+923001234567", "email": "info@acme.pk", "source": "google_maps", "social_links": {}, "lat": 24.8, "lon": 67.0},
            {"name": "New Clinic", "phone": "+923009999999", "email": "hi@newclinic.pk", "source": "google_maps", "social_links": {}, "lat": 24.8, "lon": 67.0},
        ]

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)
    monkeypatch.setattr(enrichment_jobs, "create_enrichment_job", _fake_job_store_unavailable())
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)

    async with client_factory("user_already_imported") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        # Already have Acme Dental in the CRM (e.g. imported yesterday).
        await client.post("/api/v1/leads", json={"name": "Acme Dental", "email": "info@acme.pk"})

        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 2},
        )

    assert resp.status_code == 200
    items = {i["name"]: i for i in resp.json()["items"]}
    assert items["Acme Dental"]["already_in_workspace"] is True
    assert items["New Clinic"]["already_in_workspace"] is False


async def test_already_imported_flag_matches_by_phone_too(client_factory, monkeypatch):
    async def fake_discover(niche, city, country, country_code="PK", limit=50):
        return [{"name": "Acme Dental", "phone": "+923001234567", "email": None, "source": "google_maps", "social_links": {}, "lat": 24.8, "lon": 67.0}]

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)
    monkeypatch.setattr(enrichment_jobs, "create_enrichment_job", _fake_job_store_unavailable())
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)

    async with client_factory("user_already_imported_phone") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.post("/api/v1/leads", json={"name": "Acme Dental (dup)", "phone": "+923001234567"})

        resp = await client.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )

    assert resp.json()["items"][0]["already_in_workspace"] is True


async def test_already_imported_flag_is_workspace_scoped(client_factory, monkeypatch):
    """A lead imported by Workspace X must not mark the same business as
    already-in-CRM for Workspace Y — the shared cache is global, but the
    already_in_workspace annotation must not leak across workspaces."""
    async def fake_discover(niche, city, country, country_code="PK", limit=50):
        return [{"name": "Acme Dental", "phone": "+923001234567", "email": "info@acme.pk", "source": "google_maps", "social_links": {}, "lat": 24.8, "lon": 67.0}]

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)
    monkeypatch.setattr(enrichment_jobs, "create_enrichment_job", _fake_job_store_unavailable())
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)

    async with client_factory("user_ws_x") as client_x:
        await client_x.post("/api/v1/workspaces", json={"name": "Workspace X"})
        await client_x.post("/api/v1/leads", json={"name": "Acme Dental", "email": "info@acme.pk"})

    async with client_factory("user_ws_y") as client_y:
        await client_y.post("/api/v1/workspaces", json={"name": "Workspace Y"})
        resp = await client_y.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )

    assert resp.json()["items"][0]["already_in_workspace"] is False


async def test_already_imported_flag_applied_on_cache_hit_too(client_factory, monkeypatch):
    async def fake_discover(niche, city, country, country_code="PK", limit=50):
        return [{"name": "Acme Dental", "phone": "+923001234567", "email": "info@acme.pk", "source": "google_maps", "social_links": {}, "lat": 24.8, "lon": 67.0}]

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)
    monkeypatch.setattr(enrichment_jobs, "create_enrichment_job", _fake_job_store_unavailable())
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)

    async with client_factory("user_cache_flag_1") as client_a:
        await client_a.post("/api/v1/workspaces", json={"name": "A"})
        # Warm the shared cache from workspace A's search.
        await client_a.post(
            "/api/v1/leads/discover",
            json={"niche": "Dental Clinic", "country": "PK", "city": "Karachi", "limit": 1},
        )

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
