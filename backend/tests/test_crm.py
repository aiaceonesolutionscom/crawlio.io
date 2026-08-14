from app.services.enrichment import enrichment_pipeline
from app.workers.tasks_enrichment import enrich_lead
from app.workers.tasks_scoring import score_lead_task


async def test_ai_filter_enrich_falls_back_to_inline_when_celery_unavailable(client_factory, monkeypatch):
    """Regression test: enrich_lead.delay() used to be called with no error
    handling in ai_filter_enrich, so a Redis/Celery outage crashed the request
    with a 500 whose response never passed back through CORSMiddleware (the
    browser reported this as a CORS error). Must fall back to running
    enrichment synchronously in the request instead."""
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    def _raise(lead_id):
        raise Exception("Error 10061 connecting to localhost:6379")

    monkeypatch.setattr(enrich_lead, "delay", _raise)

    async def fake_enrich_item(item, **kwargs):
        return {"phone": "+15551234567", "enrichment_status": "done"}

    monkeypatch.setattr(enrichment_pipeline, "enrich_item", fake_enrich_item)

    async with client_factory("user_ai_filter_fallback") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        ws = (await client.get("/api/v1/workspaces/me")).json()
        await client.patch(f"/api/v1/workspaces/{ws['id']}/plan", json={"plan": "pro"})

        created = await client.post("/api/v1/leads", json={"name": "No Contact"})
        lead_id = created.json()["id"]

        resp = await client.post("/api/v1/leads/ai-filter/enrich", json={"lead_ids": [lead_id]})
        updated = await client.get(f"/api/v1/leads/{lead_id}")

    assert resp.status_code == 200
    assert resp.json() == {"dispatched": 1}
    assert updated.json()["phone"] == "+15551234567"


async def test_ai_filter_splits_by_website(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_ai_filter") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        ws = (await client.get("/api/v1/workspaces/me")).json()
        await client.patch(f"/api/v1/workspaces/{ws['id']}/plan", json={"plan": "pro"})

        await client.post("/api/v1/leads", json={"name": "Has Site", "website": "https://example.com"})
        await client.post("/api/v1/leads", json={"name": "No Site"})

        resp = await client.get("/api/v1/leads/ai-filter")

    assert resp.status_code == 200
    body = resp.json()
    assert [l["name"] for l in body["with_website"]] == ["Has Site"]
    assert [l["name"] for l in body["without_website"]] == ["No Site"]


async def test_ai_filter_requires_pro_plan(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_ai_filter_free") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.get("/api/v1/leads/ai-filter")

    assert resp.status_code == 403


async def test_add_to_crm_and_list(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_crm") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        ws = (await client.get("/api/v1/workspaces/me")).json()
        await client.patch(f"/api/v1/workspaces/{ws['id']}/plan", json={"plan": "pro"})

        created = await client.post("/api/v1/leads", json={"name": "Alice", "website": "https://alice.co"})
        lead_id = created.json()["id"]

        add_resp = await client.post("/api/v1/crm/entries", json={"lead_ids": [lead_id]})
        assert add_resp.status_code == 200
        assert add_resp.json() == {"added": 1, "skipped": 0}

        # adding the same lead again should be skipped, not duplicated
        add_again = await client.post("/api/v1/crm/entries", json={"lead_ids": [lead_id]})
        assert add_again.json() == {"added": 0, "skipped": 1}

        list_resp = await client.get("/api/v1/crm/entries")

    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 1
    assert body["items"][0]["lead"]["name"] == "Alice"
    assert body["items"][0]["category"] == "with_website"


async def test_deleting_a_lead_removes_its_crm_entry(client_factory, monkeypatch):
    """A lead removed from Lead Center must not leave a dangling CRM entry
    behind — CrmEntry.lead has no DB-level cascade, so without an explicit
    cleanup the CRM list would try to render a lead that no longer exists."""
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_crm_delete") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        ws = (await client.get("/api/v1/workspaces/me")).json()
        await client.patch(f"/api/v1/workspaces/{ws['id']}/plan", json={"plan": "pro"})

        created = await client.post("/api/v1/leads", json={"name": "Bob", "website": "https://bob.co"})
        lead_id = created.json()["id"]
        await client.post("/api/v1/crm/entries", json={"lead_ids": [lead_id]})

        delete_resp = await client.delete(f"/api/v1/leads/{lead_id}")
        assert delete_resp.status_code == 204

        list_resp = await client.get("/api/v1/crm/entries")

    assert list_resp.status_code == 200
    assert list_resp.json() == {"items": [], "total": 0}


async def test_delete_all_leads_removes_their_crm_entries(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_crm_delete_all") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        ws = (await client.get("/api/v1/workspaces/me")).json()
        await client.patch(f"/api/v1/workspaces/{ws['id']}/plan", json={"plan": "pro"})

        created = await client.post("/api/v1/leads", json={"name": "Carol", "website": "https://carol.co"})
        lead_id = created.json()["id"]
        await client.post("/api/v1/crm/entries", json={"lead_ids": [lead_id]})

        delete_resp = await client.delete("/api/v1/leads")
        assert delete_resp.status_code == 200

        list_resp = await client.get("/api/v1/crm/entries")

    assert list_resp.status_code == 200
    assert list_resp.json() == {"items": [], "total": 0}
