from app.core.plans import PLAN_LIMITS
from app.workers.tasks_scoring import score_lead_task


async def test_create_lead_enqueues_scoring(client_factory, monkeypatch):
    enqueued = []
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: enqueued.append(lead_id))

    async with client_factory("user_create") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.post("/api/v1/leads", json={"name": "Amara Okafor", "company": "Northwind"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Amara Okafor"
    assert body["status"] == "New"
    assert body["score"] is None
    assert body["scoring_failed"] is False
    assert enqueued == [body["id"]]


async def test_leads_are_isolated_per_workspace(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_a") as client_a:
        await client_a.post("/api/v1/workspaces", json={"name": "Workspace A"})
        await client_a.post("/api/v1/leads", json={"name": "Alice"})

    async with client_factory("user_b") as client_b:
        await client_b.post("/api/v1/workspaces", json={"name": "Workspace B"})
        await client_b.post("/api/v1/leads", json={"name": "Bob"})
        resp_b = await client_b.get("/api/v1/leads")

    names_b = [item["name"] for item in resp_b.json()["items"]]
    assert names_b == ["Bob"]

    async with client_factory("user_a") as client_a_again:
        resp_a = await client_a_again.get("/api/v1/leads")
    names_a = [item["name"] for item in resp_a.json()["items"]]
    assert names_a == ["Alice"]


async def test_lead_search_filters_by_name_and_email(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_search") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.post("/api/v1/leads", json={"name": "Priya Raman", "email": "priya@loopretail.com"})
        await client.post("/api/v1/leads", json={"name": "Tomas Ferreira", "email": "tomas@cascadesolar.com"})

        resp = await client.get("/api/v1/leads", params={"search": "loopretail"})

    names = [item["name"] for item in resp.json()["items"]]
    assert names == ["Priya Raman"]


async def test_lead_quota_enforced_at_403(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)
    monkeypatch.setitem(PLAN_LIMITS["free"], "leads", 2)

    async with client_factory("user_quota") as client:
        await client.post("/api/v1/workspaces", json={"name": "Quota Test"})
        r1 = await client.post("/api/v1/leads", json={"name": "Lead 1"})
        r2 = await client.post("/api/v1/leads", json={"name": "Lead 2"})
        r3 = await client.post("/api/v1/leads", json={"name": "Lead 3"})

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r3.status_code == 403


async def test_get_update_delete_lead(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_crud") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        created = await client.post("/api/v1/leads", json={"name": "Alice", "email": "alice@example.com"})
        lead_id = created.json()["id"]

        got = await client.get(f"/api/v1/leads/{lead_id}")
        assert got.status_code == 200
        assert got.json()["name"] == "Alice"

        updated = await client.patch(f"/api/v1/leads/{lead_id}", json={"name": "Alice Updated", "status": "Qualified"})
        assert updated.status_code == 200
        assert updated.json()["name"] == "Alice Updated"
        assert updated.json()["status"] == "Qualified"

        deleted = await client.delete(f"/api/v1/leads/{lead_id}")
        assert deleted.status_code == 204

        missing = await client.get(f"/api/v1/leads/{lead_id}")
        assert missing.status_code == 404


async def test_delete_all_leads(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_delete_all") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.post("/api/v1/leads", json={"name": "Alice"})
        await client.post("/api/v1/leads", json={"name": "Bob"})

        resp = await client.delete("/api/v1/leads")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2

        listed = await client.get("/api/v1/leads")
        assert listed.json()["total"] == 0


async def test_duplicate_email_rejected(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_dup") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        r1 = await client.post("/api/v1/leads", json={"name": "Alice", "email": "same@example.com"})
        r2 = await client.post("/api/v1/leads", json={"name": "Bob", "email": "same@example.com"})

    assert r1.status_code == 201
    assert r2.status_code == 409


async def test_list_leads_pagination(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_page") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        for i in range(5):
            await client.post("/api/v1/leads", json={"name": f"Lead {i}"})

        page1 = await client.get("/api/v1/leads", params={"page": 1, "limit": 2})
        page2 = await client.get("/api/v1/leads", params={"page": 2, "limit": 2})

    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["items"]) == 2
    assert body1["total"] == 5
    assert body1["page"] == 1

    body2 = page2.json()
    assert len(body2["items"]) == 2
    assert body2["page"] == 2


async def test_whatsapp_requires_pro_plan(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_wa") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        created = await client.post("/api/v1/leads", json={"name": "Alice", "phone": "+14155550132"})
        lead_id = created.json()["id"]
        resp = await client.post(f"/api/v1/leads/{lead_id}/whatsapp")

    assert resp.status_code == 403


async def test_enrich_leads_fills_gaps_from_website(client_factory, monkeypatch):
    from app.services import website_scraper_service

    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async def fake_extract(url):
        return {"email": "found@example.com", "phone": "+15551234567", "social_links": {"facebook": "https://facebook.com/x"}}

    monkeypatch.setattr(website_scraper_service, "extract_contact_from_website", fake_extract)

    async with client_factory("user_enrich") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        created = await client.post(
            "/api/v1/leads", json={"name": "No Contact Yet", "website": "https://noemail.example.com"}
        )
        lead_id = created.json()["id"]

        resp = await client.post("/api/v1/leads/enrich", json={"lead_ids": [lead_id]})
        assert resp.status_code == 200
        assert resp.json() == {"enriched": 1, "unchanged": 0}

        updated = await client.get(f"/api/v1/leads/{lead_id}")

    body = updated.json()
    assert body["email"] == "found@example.com"
    assert body["phone"] == "+15551234567"
    assert body["social_links"] == {"facebook": "https://facebook.com/x"}


async def test_enrich_leads_does_not_overwrite_existing_data(client_factory, monkeypatch):
    from app.services import website_scraper_service

    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async def fake_extract(url):
        return {"email": "scraped@example.com", "phone": "+15559999999"}

    monkeypatch.setattr(website_scraper_service, "extract_contact_from_website", fake_extract)

    async with client_factory("user_enrich_noop") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        created = await client.post(
            "/api/v1/leads",
            json={"name": "Already Complete", "email": "real@example.com", "website": "https://example.com"},
        )
        lead_id = created.json()["id"]

        resp = await client.post("/api/v1/leads/enrich", json={"lead_ids": [lead_id]})
        assert resp.json()["enriched"] == 1  # phone still got filled in

        updated = await client.get(f"/api/v1/leads/{lead_id}")

    assert updated.json()["email"] == "real@example.com"  # untouched
    assert updated.json()["phone"] == "+15559999999"  # gap filled
