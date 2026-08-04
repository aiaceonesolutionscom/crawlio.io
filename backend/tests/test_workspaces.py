async def test_create_workspace_defaults_to_free(authed_client):
    resp = await authed_client.post("/api/v1/workspaces", json={"name": "Acme Workspace"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["plan"] == "free"
    assert body["lead_quota"] == 500
    assert body["seat_quota"] == 1


async def test_create_workspace_ignores_client_supplied_plan(authed_client):
    resp = await authed_client.post(
        "/api/v1/workspaces", json={"name": "Acme Workspace", "plan": "enterprise"}
    )
    assert resp.status_code == 201
    assert resp.json()["plan"] == "free"


async def test_create_workspace_is_idempotent(authed_client):
    first = await authed_client.post("/api/v1/workspaces", json={"name": "Acme Workspace"})
    second = await authed_client.post("/api/v1/workspaces", json={"name": "Different Name"})
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["name"] == "Acme Workspace"


async def test_get_my_workspace_404_before_creation(authed_client):
    resp = await authed_client.get("/api/v1/workspaces/me")
    assert resp.status_code == 404


async def test_get_my_workspace_after_creation(authed_client):
    await authed_client.post("/api/v1/workspaces", json={"name": "Acme Workspace"})
    resp = await authed_client.get("/api/v1/workspaces/me")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Acme Workspace"


async def test_update_plan(authed_client):
    created = await authed_client.post("/api/v1/workspaces", json={"name": "Acme"})
    workspace_id = created.json()["id"]

    resp = await authed_client.patch(f"/api/v1/workspaces/{workspace_id}/plan", json={"plan": "pro"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "pro"
    assert body["lead_quota"] == 5000
    assert body["seat_quota"] == 10


async def test_update_plan_rejects_mismatched_workspace_id(authed_client):
    await authed_client.post("/api/v1/workspaces", json={"name": "Acme"})
    resp = await authed_client.patch("/api/v1/workspaces/not-my-workspace-id/plan", json={"plan": "pro"})
    assert resp.status_code == 403
