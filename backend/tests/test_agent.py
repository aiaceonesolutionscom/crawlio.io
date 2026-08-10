from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models.agent import BusinessProfile, Meeting
from app.db.models.email import EmailMessage
from app.db.models.lead import Lead
from app.db.models.workspace import Workspace
from app.services import business_profile_service, meeting_service, outreach_service
from app.services.email_ai_service import _is_unsubscribe_message
from app.workers.tasks_scoring import score_lead_task

USER = "user_agent_test"


async def _make_workspace(client) -> Workspace:
    await client.post("/api/v1/workspaces", json={"name": "Acme"})
    ws = (await client.get("/api/v1/workspaces/me")).json()
    await client.patch(f"/api/v1/workspaces/{ws['id']}/plan", json={"plan": "pro"})
    return ws


# ---------- meeting slot generation (pure) ----------

def test_next_slots_respect_business_hours_and_books():
    profile = BusinessProfile(
        business_name="Acme",
        owner_name="Nauman",
        timezone="UTC",
        business_hours={"monday": ["09:00", "10:00"], "tuesday": ["09:00", "10:00"]},
    )
    now = datetime(2026, 8, 10, 8, 30, tzinfo=timezone.utc)  # Monday 08:30 UTC
    slots = meeting_service.next_slots(profile, now=now, count=4)
    assert len(slots) == 4
    # Never before opening, never at/after closing.
    for s in slots:
        assert s.hour >= 9
        assert not (s.hour == 10 and s.minute >= 0)


def test_unsubscribe_detection_keywords():
    assert _is_unsubscribe_message("please unsubscribe me from your emails")
    assert _is_unsubscribe_message("Do not contact me again.")
    assert _is_unsubscribe_message("kindly remove me from your list")
    assert not _is_unsubscribe_message("I am interested in your services")


# ---------- business profile persistence ----------

async def test_business_profile_create_get_persists(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory(USER) as client:
        ws = await _make_workspace(client)
        resp = await client.post("/api/v1/business-profile", json={
            "business_name": "AceOne",
            "owner_name": "Nauman Alvi",
            "business_phone": "+921234567890",
            "business_address": "Karachi, Pakistan",
            "services": "AI automation, lead generation, email outreach",
            "timezone": "Asia/Karachi",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["business_name"] == "AceOne"
        assert body["owner_name"] == "Nauman Alvi"

        # Second create -> conflict
        dup = await client.post("/api/v1/business-profile", json={
            "business_name": "B", "owner_name": "C",
        })
        assert dup.status_code == 409

        # Persistence: re-fetch through a fresh request
        got = await client.get("/api/v1/business-profile")
        assert got.status_code == 200
        assert got.json()["business_name"] == "AceOne"

        # Update edits in place
        upd = await client.put("/api/v1/business-profile", json={
            "business_name": "AceOne Ltd", "owner_name": "Nauman Alvi",
            "services": "AI automation",
        })
        assert upd.status_code == 200
        assert upd.json()["business_name"] == "AceOne Ltd"


async def test_business_profile_requires_email_agent_plan(client_factory, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_agent_free") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.get("/api/v1/business-profile")

    assert resp.status_code == 403


# ---------- eligible leads / dedup / unsubscribe / usage ----------

async def test_eligible_leads_excludes_contacted_and_unsubscribed(db_engine, monkeypatch):
    session_maker = __import__("sqlalchemy").ext.asyncio.async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        ws = Workspace(name="Acme", plan="pro", lead_quota=500, seat_quota=1)
        session.add(ws)
        await session.flush()

        fresh = Lead(workspace_id=ws.id, name="John", email="john@example.com", website="https://john.co")
        contacted = Lead(workspace_id=ws.id, name="Mary", email="mary@example.com", outreach_sent_at=datetime.now(timezone.utc))
        unsub = Lead(workspace_id=ws.id, name="Sam", email="sam@example.com", unsubscribed_at=datetime.now(timezone.utc))
        no_email = Lead(workspace_id=ws.id, name="NoMail")
        session.add_all([fresh, contacted, unsub, no_email])
        await session.flush()

        eligible = await outreach_service.eligible_leads(session, ws.id)

        assert [l.name for l in eligible] == ["John"]
        assert outreach_service.lead_source(fresh) == "website"
        assert outreach_service.lead_source(contacted) == "non-website"


async def test_outreach_usage_counts_today_only(db_engine, monkeypatch):
    session_maker = __import__("sqlalchemy").ext.asyncio.async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        ws = Workspace(name="Acme2", plan="pro", lead_quota=500, seat_quota=1)
        session.add(ws)
        await session.flush()
        now = datetime.now(timezone.utc)
        session.add(EmailMessage(workspace_id=ws.id, to_email="a@x.com", subject="s", kind="outreach", status="sent", sent_at=now))
        session.add(EmailMessage(workspace_id=ws.id, to_email="b@x.com", subject="s", kind="outreach", status="sent", sent_at=now))
        session.add(EmailMessage(workspace_id=ws.id, to_email="c@x.com", subject="s", kind="composed", status="sent", sent_at=now))
        await session.flush()

        used = await outreach_service.outreach_used_today(session, ws.id, "Asia/Karachi")
        assert used == 2

        from app.core.config import settings
        assert outreach_service.outreach_daily_limit(ws) == settings.pro_daily_email_limit


async def test_validate_send_rejects_unsubscribed_and_limit(db_engine, monkeypatch):
    monkeypatch.setattr(outreach_service, "outreach_used_today", lambda session, ws, tz: 100)
    session_maker = __import__("sqlalchemy").ext.asyncio.async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        ws = Workspace(name="AcmeVal", plan="pro", lead_quota=500, seat_quota=1)
        session.add(ws)
        await session.flush()
        lead = Lead(workspace_id=ws.id, name="John", email="john@example.com", website="https://j.co")
        session.add(lead)
        await session.flush()
        profile = await business_profile_service.create_profile(session, ws.id, "Acme", "N", timezone="Asia/Karachi")
        with pytest.raises(Exception):
            await outreach_service.send_outreach(session, ws, profile, lead, "Hi", "Body")