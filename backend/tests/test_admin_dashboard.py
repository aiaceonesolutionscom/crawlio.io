from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models.workspace import Workspace
from app.workers.tasks_scoring import score_lead_task


async def test_dashboard_overview_empty(admin_client):
    resp = await admin_client.get("/api/v1/admin/dashboard/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_workspaces"] == 0
    assert body["total_leads"] == 0
    assert body["workspaces_by_plan"] == []
    assert len(body["new_workspaces_over_time"]) == 8
    # admin_client's own seeded PlatformAdmin counts as active
    assert body["active_platform_admins"] == 1


async def test_dashboard_groups_by_plan_and_counts_leads(admin_client, client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_dash_a") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.post("/api/v1/leads", json={"name": "Lead 1"})
        await client.post("/api/v1/leads", json={"name": "Lead 2"})

    async with client_factory("user_dash_b") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Beta Co"})
        await client.patch(f"/api/v1/workspaces/{created.json()['id']}/plan", json={"plan": "pro"})
        await client.post("/api/v1/leads", json={"name": "Lead 3"})

    resp = await admin_client.get("/api/v1/admin/dashboard/overview")
    body = resp.json()
    assert body["total_workspaces"] == 2
    assert body["total_leads"] == 3
    plan_counts = {p["plan"]: p["count"] for p in body["workspaces_by_plan"]}
    assert plan_counts == {"free": 1, "pro": 1}


async def test_dashboard_boundary_workspace_lands_in_current_bucket(admin_client, client_factory, db_engine):
    async with client_factory("user_dash_boundary") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Boundary Co"})
        workspace_id = created.json()["id"]

    # Simulate a workspace created exactly "now" relative to when the overview
    # endpoint computes its own now() a moment later — this is the scenario
    # that silently dropped records under the old strict `<` upper bound.
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(
            update(Workspace).where(Workspace.id == workspace_id).values(created_at=datetime.now(timezone.utc))
        )
        await session.commit()

    resp = await admin_client.get("/api/v1/admin/dashboard/overview")
    body = resp.json()
    latest_week = body["new_workspaces_over_time"][-1]
    assert latest_week["count"] == 1
