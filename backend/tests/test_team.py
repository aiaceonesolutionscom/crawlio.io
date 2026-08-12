from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models.plan_config import PlanConfig
from app.workers.tasks_email import send_invite_email_task, send_welcome_email_task


async def test_team_requires_pro_plan(client_factory):
    async with client_factory("user_team_free") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.get("/api/v1/team/members")

    assert resp.status_code == 403


async def test_invite_member_creates_pending_entry(client_factory, monkeypatch):
    monkeypatch.setattr(send_invite_email_task, "delay", lambda *args: None)

    async with client_factory("user_team_owner") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        workspace_id = created.json()["id"]
        await client.patch(f"/api/v1/workspaces/{workspace_id}/plan", json={"plan": "pro"})

        resp = await client.post("/api/v1/team/invites", json={"email": "new@acme.com", "role": "Member"})
        listed = await client.get("/api/v1/team/members")

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "Invited"
    assert body["email"] == "new@acme.com"

    items = listed.json()["items"]
    statuses = {item["email"]: item["status"] for item in items}
    assert statuses["new@acme.com"] == "Invited"
    # owner's own membership row should also be listed as Active
    assert any(item["status"] == "Active" for item in items)


async def test_invite_member_email_dispatch_failure_does_not_crash(client_factory, monkeypatch):
    """Regression test: send_invite_email_task.delay() used to be called with
    no error handling -- a Redis outage must not stop a team invite from
    being created."""
    def _raise(*args):
        raise Exception("Error 10061 connecting to localhost:6379")

    monkeypatch.setattr(send_invite_email_task, "delay", _raise)

    async with client_factory("user_team_owner_no_redis") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        workspace_id = created.json()["id"]
        await client.patch(f"/api/v1/workspaces/{workspace_id}/plan", json={"plan": "pro"})

        resp = await client.post("/api/v1/team/invites", json={"email": "new2@acme.com", "role": "Member"})

    assert resp.status_code == 201
    assert resp.json()["status"] == "Invited"


async def test_invite_enforces_seat_quota(client_factory, db_engine, monkeypatch):
    monkeypatch.setattr(send_invite_email_task, "delay", lambda *args: None)

    # seat_quota is copied onto the workspace row from plan_configs at
    # plan-change time, so lower the seeded "pro" limit before upgrading below.
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(update(PlanConfig).where(PlanConfig.plan_key == "pro").values(seat_quota=2))
        await session.commit()

    async with client_factory("user_team_quota") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        workspace_id = created.json()["id"]
        await client.patch(f"/api/v1/workspaces/{workspace_id}/plan", json={"plan": "pro"})

        first = await client.post("/api/v1/team/invites", json={"email": "one@acme.com"})
        second = await client.post("/api/v1/team/invites", json={"email": "two@acme.com"})

    assert first.status_code == 201
    assert second.status_code == 403


async def test_invite_duplicate_email_conflicts(client_factory, monkeypatch):
    monkeypatch.setattr(send_invite_email_task, "delay", lambda *args: None)

    async with client_factory("user_team_dup") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.patch(f"/api/v1/workspaces/{created.json()['id']}/plan", json={"plan": "pro"})

        await client.post("/api/v1/team/invites", json={"email": "dup@acme.com"})
        second = await client.post("/api/v1/team/invites", json={"email": "dup@acme.com"})

    assert second.status_code == 409


async def test_remove_pending_invite(client_factory, monkeypatch):
    monkeypatch.setattr(send_invite_email_task, "delay", lambda *args: None)

    async with client_factory("user_team_remove") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.patch(f"/api/v1/workspaces/{created.json()['id']}/plan", json={"plan": "pro"})

        invite = await client.post("/api/v1/team/invites", json={"email": "gone@acme.com"})
        deleted = await client.delete(f"/api/v1/team/members/{invite.json()['id']}")
        listed = await client.get("/api/v1/team/members")

    assert deleted.status_code == 204
    assert all(item["email"] != "gone@acme.com" for item in listed.json()["items"])


async def test_cannot_remove_owner(client_factory):
    async with client_factory("user_team_owner_guard") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        workspace_id = created.json()["id"]
        await client.patch(f"/api/v1/workspaces/{workspace_id}/plan", json={"plan": "pro"})

        listed = await client.get("/api/v1/team/members")
        owner_entry = next(item for item in listed.json()["items"] if item["status"] == "Active")
        resp = await client.delete(f"/api/v1/team/members/{owner_entry['id']}")

    assert resp.status_code == 400


async def test_invited_user_joins_existing_workspace_on_signup(client_factory, monkeypatch):
    monkeypatch.setattr(send_invite_email_task, "delay", lambda *args: None)
    monkeypatch.setattr(send_welcome_email_task, "delay", lambda *args: None)

    async with client_factory("user_team_inviter") as owner_client:
        created = await owner_client.post(
            "/api/v1/workspaces", json={"name": "Acme", "owner_email": "owner@acme.com"}
        )
        workspace_id = created.json()["id"]
        await owner_client.patch(f"/api/v1/workspaces/{workspace_id}/plan", json={"plan": "pro"})
        await owner_client.post("/api/v1/team/invites", json={"email": "invitee@acme.com", "role": "Admin"})

    async with client_factory("user_team_invitee") as invitee_client:
        joined = await invitee_client.post(
            "/api/v1/workspaces",
            json={"name": "Ignored Name", "owner_email": "invitee@acme.com", "owner_name": "Invitee"}
        )

    assert joined.status_code == 201
    assert joined.json()["id"] == workspace_id
    assert joined.json()["name"] == "Acme"

    async with client_factory("user_team_inviter") as owner_client:
        listed = await owner_client.get("/api/v1/team/members")

    invitee_entry = next(item for item in listed.json()["items"] if item["email"] == "invitee@acme.com")
    assert invitee_entry["status"] == "Active"
    assert invitee_entry["role"] == "Admin"
