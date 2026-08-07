import asyncio

import pytest
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
            session, workspace, LeadCreate(name="Amara Okafor")
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


async def test_score_lead_async_propagates_failure_without_partial_writes(db_engine, monkeypatch):
    """_score_lead_async intentionally lets scoring errors bubble up now — retry/backoff
    and the final scoring_failed state are handled one level up, by score_lead_task."""
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

    with pytest.raises(RuntimeError):
        await tasks_scoring._score_lead_async(lead_id)

    async with session_maker() as session:
        result = await session.execute(select(Lead).where(Lead.id == lead_id))
        updated = result.scalar_one()
        assert updated.score is None
        assert updated.status == "New"


async def test_score_lead_async_ignores_missing_lead(db_engine, monkeypatch):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(tasks_scoring, "async_session_maker", session_maker)

    await tasks_scoring._score_lead_async("does-not-exist")  # must not raise


def test_score_lead_task_retries_then_marks_failed_after_max_retries(db_engine, monkeypatch):
    """Persistent Mistral failure should retry MAX_SCORING_RETRIES times, then flag
    the lead as scoring_failed instead of leaving it silently unscored forever.

    Runs synchronously (not `async def`) because score_lead_task.apply() calls
    asyncio.run() internally on every retry, same as a real Celery worker does —
    that can't nest inside pytest-asyncio's own event loop.
    """
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _create_lead() -> str:
        async with session_maker() as session:
            workspace = Workspace(id="ws_retry", name="Acme", plan="free", lead_quota=500, seat_quota=1)
            session.add(workspace)
            await session.flush()
            session.add(WorkspaceMember(workspace_id=workspace.id, user_id="user_retry", role="Owner"))
            await session.commit()

            lead = await lead_service.create_lead(session, workspace, LeadCreate(name="Retry Test"))
            return lead.id

    lead_id = asyncio.run(_create_lead())

    attempts = {"count": 0}

    async def always_failing_score_lead(*args, **kwargs):
        attempts["count"] += 1
        raise RuntimeError("Mistral is down")

    monkeypatch.setattr(tasks_scoring.scoring_service, "score_lead", always_failing_score_lead)
    monkeypatch.setattr(tasks_scoring, "async_session_maker", session_maker)

    # .apply() runs the task (and Celery's real eager retry loop) synchronously in-process,
    # with no broker and no actual sleeping between retries.
    tasks_scoring.score_lead_task.apply(args=[lead_id])

    assert attempts["count"] == tasks_scoring.MAX_SCORING_RETRIES + 1  # initial attempt + retries

    async def _check() -> Lead:
        async with session_maker() as session:
            result = await session.execute(select(Lead).where(Lead.id == lead_id))
            return result.scalar_one()

    updated = asyncio.run(_check())
    assert updated.score is None
    assert (updated.lead_metadata or {}).get("scoring_failed") is True
