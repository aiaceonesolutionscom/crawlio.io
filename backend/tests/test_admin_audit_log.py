async def test_audit_log_records_and_lists_plan_config_edit(admin_client):
    resp = await admin_client.patch(
        "/api/v1/admin/plan-configs/free", json={"lead_quota": 750}
    )
    assert resp.status_code == 200

    listed = await admin_client.get("/api/v1/admin/audit-log")
    assert listed.status_code == 200
    entries = listed.json()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["action"] == "plan_config.update"
    assert entry["target_type"] == "plan_config"
    assert entry["target_id"] == "free"
    assert entry["before"]["lead_quota"] == 500
    assert entry["after"]["lead_quota"] == 750


async def test_audit_log_filters_by_action_and_target_type(admin_client):
    await admin_client.patch("/api/v1/admin/plan-configs/free", json={"lead_quota": 600})
    await admin_client.patch("/api/v1/admin/plan-configs/pro", json={"lead_quota": 6000})

    matching = await admin_client.get(
        "/api/v1/admin/audit-log", params={"action": "plan_config.update", "target_type": "plan_config"}
    )
    assert len(matching.json()) == 2

    none_matching = await admin_client.get("/api/v1/admin/audit-log", params={"action": "workspace.delete"})
    assert none_matching.json() == []
