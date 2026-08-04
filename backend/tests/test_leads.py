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


async def test_lead_search_filters_by_name_company_email(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_search") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.post("/api/v1/leads", json={"name": "Priya Raman", "company": "Loop Retail"})
        await client.post("/api/v1/leads", json={"name": "Tomas Ferreira", "company": "Cascade Solar"})

        resp = await client.get("/api/v1/leads", params={"search": "loop"})

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
