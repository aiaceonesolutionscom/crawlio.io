from sqlalchemy.ext.asyncio import async_sessionmaker

from app.services import feature_flag_service


async def _create_workspace(client_factory, user_id: str) -> str:
    async with client_factory(user_id) as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        return created.json()["id"]


async def test_create_flag_and_reject_duplicate_key(admin_client):
    resp = await admin_client.post(
        "/api/v1/admin/feature-flags", json={"key": "beta_ui", "description": "New UI", "default_enabled": False}
    )
    assert resp.status_code == 201
    assert resp.json()["key"] == "beta_ui"

    dup = await admin_client.post(
        "/api/v1/admin/feature-flags", json={"key": "beta_ui", "default_enabled": True}
    )
    assert dup.status_code == 400


async def test_update_flag_default_enabled(admin_client):
    created = await admin_client.post("/api/v1/admin/feature-flags", json={"key": "beta_ui"})
    flag_id = created.json()["id"]

    updated = await admin_client.patch(f"/api/v1/admin/feature-flags/{flag_id}", json={"default_enabled": True})
    assert updated.status_code == 200
    assert updated.json()["default_enabled"] is True


async def test_delete_flag_cascades_overrides(admin_client, client_factory):
    workspace_id = await _create_workspace(client_factory, "user_ff_delete")

    created = await admin_client.post("/api/v1/admin/feature-flags", json={"key": "beta_ui"})
    flag_id = created.json()["id"]

    await admin_client.put(
        f"/api/v1/admin/feature-flags/{flag_id}/overrides",
        json={"workspace_id": workspace_id, "is_enabled": True},
    )

    delete_resp = await admin_client.delete(f"/api/v1/admin/feature-flags/{flag_id}")
    assert delete_resp.status_code == 204

    overrides_resp = await admin_client.get(f"/api/v1/admin/feature-flags/{flag_id}/overrides")
    assert overrides_resp.status_code == 404


async def test_set_and_clear_override(admin_client, client_factory):
    workspace_id = await _create_workspace(client_factory, "user_ff_override")

    created = await admin_client.post("/api/v1/admin/feature-flags", json={"key": "beta_ui"})
    flag_id = created.json()["id"]

    set_resp = await admin_client.put(
        f"/api/v1/admin/feature-flags/{flag_id}/overrides",
        json={"workspace_id": workspace_id, "is_enabled": True},
    )
    assert set_resp.status_code == 200
    assert set_resp.json()["is_enabled"] is True

    listed = await admin_client.get(f"/api/v1/admin/feature-flags/{flag_id}/overrides")
    assert len(listed.json()) == 1

    clear_resp = await admin_client.delete(f"/api/v1/admin/feature-flags/{flag_id}/overrides/{workspace_id}")
    assert clear_resp.status_code == 204

    listed_after = await admin_client.get(f"/api/v1/admin/feature-flags/{flag_id}/overrides")
    assert listed_after.json() == []


async def test_is_enabled_no_flag_fails_closed(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        result = await feature_flag_service.is_enabled(session, "nonexistent_flag", "ws_1")
    assert result is False


async def test_is_enabled_uses_default_when_no_override(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        flag = await feature_flag_service.create_flag(
            session, key="beta_ui", description=None, default_enabled=True
        )
        result = await feature_flag_service.is_enabled(session, flag.key, "ws_1")
    assert result is True


async def test_is_enabled_override_wins_over_default(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        flag = await feature_flag_service.create_flag(
            session, key="beta_ui", description=None, default_enabled=True
        )
        await feature_flag_service.set_override(session, flag_id=flag.id, workspace_id="ws_1", is_enabled=False)
        result = await feature_flag_service.is_enabled(session, flag.key, "ws_1")
    assert result is False
