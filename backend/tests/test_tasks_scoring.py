from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models.lead import Lead
from app.db.models.workspace import Workspace, WorkspaceMember
from app.schemas.lead import LeadCreate
from app.services import lead_service
from app.workers import tasks_scoring


async def test_score_lead_async_updates_lead(db_engine, monkeypatch):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_maker() as session:
        workspace = Workspace(id="ws_1", name="Acme", plan="free", lead_quota=500, seat_quota=1)
        session.add(workspace)
        await session.flush()
        session.add(WorkspaceMember(workspace_id=workspace.id, user_id="user_1", role="Owner"))
        await session.commit()

        lead = await lead_service.create_lead(
            session, workspace, LeadCreate(name="Amara Okafor", company="Northwind")
        )
        lead_id = lead.id

    async def fake_score_lead(name, company, email, source):
        return {"score": 91, "status": "Qualified"}

    monkeypatch.setattr(tasks_scoring.scoring_service, "score_lead", fake_score_lead)
    monkeypatch.setattr(tasks_scoring, "async_session_maker", session_maker)

    await tasks_scoring._score_lead_async(lead_id)

    async with session_maker() as session:
        result = await session.execute(select(Lead).where(Lead.id == lead_id))
        updated = result.scalar_one()
        assert updated.score == 91
        assert updated.status == "Qualified"


async def test_score_lead_async_handles_scoring_failure_gracefully(db_engine, monkeypatch):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_maker() as session:
        workspace = Workspace(id="ws_2", name="Acme2", plan="free", lead_quota=500, seat_quota=1)
        session.add(workspace)
        await session.flush()
        session.add(WorkspaceMember(workspace_id=workspace.id, user_id="user_2", role="Owner"))
        await session.commit()

        lead = await lead_service.create_lead(session, workspace, LeadCreate(name="Daniel Reyes"))
        lead_id = lead.id

    async def failing_score_lead(*args, **kwargs):
        raise RuntimeError("Mistral is down")

    monkeypatch.setattr(tasks_scoring.scoring_service, "score_lead", failing_score_lead)
    monkeypatch.setattr(tasks_scoring, "async_session_maker", session_maker)

    await tasks_scoring._score_lead_async(lead_id)  # must not raise

    async with session_maker() as session:
        result = await session.execute(select(Lead).where(Lead.id == lead_id))
        updated = result.scalar_one()
        assert updated.score is None
        assert updated.status == "New"


async def test_score_lead_async_ignores_missing_lead(db_engine, monkeypatch):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(tasks_scoring, "async_session_maker", session_maker)

    await tasks_scoring._score_lead_async("does-not-exist")  # must not raise
