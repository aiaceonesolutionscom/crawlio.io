from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models.email import EmailMessage
from app.db.models.workspace import Workspace
from app.workers.tasks_scoring import score_lead_task


async def test_inbound_webhook_creates_lead_with_correct_token(client_factory, db_engine, monkeypatch):
    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)

    async with client_factory("user_hook") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        workspace_id = created.json()["id"]

        session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
        async with session_maker() as session:
            result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
            token = result.scalar_one().webhook_token

        resp = await client.post(
            f"/api/v1/webhooks/leads/{workspace_id}",
            params={"token": token},
            json={"name": "Inbound Lead", "email": "lead@example.com", "source": "landing-page"}
        )
        leads_resp = await client.get("/api/v1/leads")

    assert resp.status_code == 201
    names = [item["name"] for item in leads_resp.json()["items"]]
    assert names == ["Inbound Lead"]


async def test_inbound_webhook_scoring_dispatch_failure_does_not_crash(client_factory, db_engine, monkeypatch):
    """Regression test: score_lead_task.delay() used to be called with no error
    handling here too -- a Redis outage must not stop the inbound webhook from
    capturing the lead."""
    def _raise(lead_id):
        raise Exception("Error 10061 connecting to localhost:6379")

    monkeypatch.setattr(score_lead_task, "delay", _raise)

    async with client_factory("user_hook_no_redis") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        workspace_id = created.json()["id"]

        session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
        async with session_maker() as session:
            result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
            token = result.scalar_one().webhook_token

        resp = await client.post(
            f"/api/v1/webhooks/leads/{workspace_id}",
            params={"token": token},
            json={"name": "Inbound Lead", "email": "lead2@example.com"}
        )

    assert resp.status_code == 201
    assert resp.json()["status"] == "captured"


async def test_inbound_webhook_rejects_wrong_token(client_factory):
    async with client_factory("user_hook2") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        workspace_id = created.json()["id"]

        resp = await client.post(
            f"/api/v1/webhooks/leads/{workspace_id}", params={"token": "wrong-token"}, json={"name": "X"}
        )

    assert resp.status_code == 404


async def test_brevo_webhook_updates_matching_email_message(client_factory, db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        workspace = Workspace(name="Acme")
        session.add(workspace)
        await session.flush()
        message = EmailMessage(
            workspace_id=workspace.id, to_email="a@b.com", subject="Hi", provider_message_id="brevo_msg_123"
        )
        session.add(message)
        await session.commit()
        message_id = message.id

    async with client_factory("user_hook3") as client:
        resp = await client.post(
            "/api/v1/webhooks/brevo", json={"event": "delivered", "message-id": "brevo_msg_123"}
        )

    assert resp.status_code == 200
    assert resp.json()["applied"] is True

    async with session_maker() as session:
        result = await session.execute(select(EmailMessage).where(EmailMessage.id == message_id))
        updated = result.scalar_one()
        assert updated.status == "delivered"
        assert updated.sent_at is not None


async def test_brevo_webhook_maps_bounce_events(client_factory, db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        workspace = Workspace(name="Acme")
        session.add(workspace)
        await session.flush()
        message = EmailMessage(
            workspace_id=workspace.id, to_email="a@b.com", subject="Hi", provider_message_id="brevo_msg_456"
        )
        session.add(message)
        await session.commit()
        message_id = message.id

    async with client_factory("user_hook5") as client:
        resp = await client.post(
            "/api/v1/webhooks/brevo", json={"event": "hard_bounce", "message-id": "brevo_msg_456"}
        )

    assert resp.status_code == 200
    async with session_maker() as session:
        result = await session.execute(select(EmailMessage).where(EmailMessage.id == message_id))
        assert result.scalar_one().status == "bounced"


async def test_brevo_webhook_ignores_unknown_message(client_factory):
    async with client_factory("user_hook4") as client:
        resp = await client.post(
            "/api/v1/webhooks/brevo", json={"event": "delivered", "message-id": "does-not-exist"}
        )

    assert resp.status_code == 200
    assert resp.json()["applied"] is False
