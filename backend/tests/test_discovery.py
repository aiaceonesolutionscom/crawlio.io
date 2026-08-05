from app.services import discovery_service
from app.workers.tasks_scoring import score_lead_task


FAKE_RESULTS = [
    {"name": "Bright Smile Dental", "phone": "+92 300 1234567", "email": None,
     "website": "https://brightsmile.pk", "address": "Clifton, Karachi", "source": "openstreetmap"},
    {"name": "Karachi Dental Studio", "phone": None, "email": "hello@kds.pk",
     "website": None, "address": "DHA, Karachi", "source": "openstreetmap"},
]


async def test_discover_returns_results(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async def fake_discover(niche, lat, lon, limit=50, radius_m=15000):
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


async def test_discover_unavailable_returns_503(client_factory, monkeypatch):
    async def failing_discover(niche, lat, lon, limit=50, radius_m=15000):
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
