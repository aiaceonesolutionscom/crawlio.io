from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models.lead import Lead


async def test_analytics_requires_pro_plan(client_factory):
    async with client_factory("user_analytics_free") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.get("/api/v1/analytics/overview")

    assert resp.status_code == 403


async def test_analytics_overview_empty_workspace(client_factory):
    async with client_factory("user_analytics_empty") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.patch(f"/api/v1/workspaces/{created.json()['id']}/plan", json={"plan": "pro"})
        resp = await client.get("/api/v1/analytics/overview")

    body = resp.json()
    assert body["total_leads"] == 0
    assert body["qualified_leads"] == 0
    assert body["avg_score"] == 0.0
    assert len(body["leads_over_time"]) == 8
    assert body["source_split"] == []


async def test_analytics_overview_computes_real_metrics(client_factory, db_engine):
    async with client_factory("user_analytics_real") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        workspace_id = created.json()["id"]
        await client.patch(f"/api/v1/workspaces/{workspace_id}/plan", json={"plan": "pro"})

        session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
        now = datetime.now(timezone.utc)
        async with session_maker() as session:
            session.add_all([
                Lead(workspace_id=workspace_id, name="A", score=90, status="Qualified", source="Webinar",
                     created_at=now),
                Lead(workspace_id=workspace_id, name="B", score=40, status="New", source="Webinar", created_at=now),
                Lead(workspace_id=workspace_id, name="C", score=None, status="New", source="Referral",
                     created_at=now)
            ])
            await session.commit()

        resp = await client.get("/api/v1/analytics/overview")

    body = resp.json()
    assert body["total_leads"] == 3
    assert body["qualified_leads"] == 1
    assert body["avg_score"] == 65.0

    source_by_name = {s["name"]: s["value"] for s in body["source_split"]}
    assert source_by_name["Webinar"] == 67
    assert source_by_name["Referral"] == 33

    status_counts = {s["status"]: s["count"] for s in body["status_breakdown"]}
    assert status_counts["Qualified"] == 1
    assert status_counts["New"] == 2

    latest_week = body["leads_over_time"][-1]
    assert latest_week["leads"] == 3
    assert latest_week["qualified"] == 1
