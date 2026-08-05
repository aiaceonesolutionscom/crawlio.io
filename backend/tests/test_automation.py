async def test_create_sequence_on_pro_workspace(client_factory):
    async with client_factory("user_auto") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        workspace_id = created.json()["id"]
        await client.patch(f"/api/v1/workspaces/{workspace_id}/plan", json={"plan": "pro"})

        resp = await client.post(
            "/api/v1/automation/sequences",
            json={
                "name": "Welcome flow",
                "trigger": "lead_created",
                "steps": [
                    {"subject": "Hi there", "body": "Welcome!", "delay_hours": 0},
                    {"subject": "Follow up", "body": "Still interested?", "delay_hours": 48}
                ]
            }
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert [s["subject"] for s in body["steps"]] == ["Hi there", "Follow up"]
    assert [s["step_order"] for s in body["steps"]] == [0, 1]


async def test_automation_requires_pro_plan(client_factory):
    async with client_factory("user_free_auto") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        resp = await client.get("/api/v1/automation/sequences")

    assert resp.status_code == 403


async def test_update_sequence_status_and_delete(client_factory):
    async with client_factory("user_auto2") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        workspace_id = created.json()["id"]
        await client.patch(f"/api/v1/workspaces/{workspace_id}/plan", json={"plan": "enterprise"})

        seq = await client.post("/api/v1/automation/sequences", json={"name": "Seq", "steps": []})
        seq_id = seq.json()["id"]

        activated = await client.patch(f"/api/v1/automation/sequences/{seq_id}/status", json={"status": "active"})
        assert activated.json()["status"] == "active"

        listed = await client.get("/api/v1/automation/sequences")
        assert len(listed.json()["items"]) == 1

        deleted = await client.delete(f"/api/v1/automation/sequences/{seq_id}")
        assert deleted.status_code == 204

        listed_after = await client.get("/api/v1/automation/sequences")

    assert listed_after.json()["items"] == []


async def test_sequence_status_update_404_for_unknown_id(client_factory):
    async with client_factory("user_auto3") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.patch(f"/api/v1/workspaces/{created.json()['id']}/plan", json={"plan": "pro"})
        resp = await client.patch("/api/v1/automation/sequences/does-not-exist/status", json={"status": "active"})

    assert resp.status_code == 404


async def test_sequences_are_isolated_per_workspace(client_factory):
    async with client_factory("user_auto_a") as client_a:
        ws_a = await client_a.post("/api/v1/workspaces", json={"name": "A"})
        await client_a.patch(f"/api/v1/workspaces/{ws_a.json()['id']}/plan", json={"plan": "pro"})
        await client_a.post("/api/v1/automation/sequences", json={"name": "A seq", "steps": []})

    async with client_factory("user_auto_b") as client_b:
        ws_b = await client_b.post("/api/v1/workspaces", json={"name": "B"})
        await client_b.patch(f"/api/v1/workspaces/{ws_b.json()['id']}/plan", json={"plan": "pro"})
        resp_b = await client_b.get("/api/v1/automation/sequences")

    assert resp_b.json()["items"] == []
