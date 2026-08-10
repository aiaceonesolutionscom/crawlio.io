async def test_upsert_creates_then_updates_setting(admin_client):
    created = await admin_client.put(
        "/api/v1/admin/system-settings/max_upload_mb",
        json={"value": 10, "value_type": "number", "description": "Max upload size in MB"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["key"] == "max_upload_mb"
    assert body["value"] == 10
    assert body["updated_by"] == "admin_test_fixed@crawlio.io"

    updated = await admin_client.put(
        "/api/v1/admin/system-settings/max_upload_mb", json={"value": 25, "value_type": "number"}
    )
    assert updated.status_code == 200
    assert updated.json()["value"] == 25
    # description omitted on update -> unchanged, not wiped
    assert updated.json()["description"] == "Max upload size in MB"


async def test_list_and_delete_setting(admin_client):
    await admin_client.put("/api/v1/admin/system-settings/feature_x", json={"value": True, "value_type": "boolean"})

    listed = await admin_client.get("/api/v1/admin/system-settings")
    assert any(s["key"] == "feature_x" for s in listed.json())

    deleted = await admin_client.delete("/api/v1/admin/system-settings/feature_x")
    assert deleted.status_code == 204

    listed_after = await admin_client.get("/api/v1/admin/system-settings")
    assert not any(s["key"] == "feature_x" for s in listed_after.json())


async def test_upsert_records_audit_trail(admin_client):
    await admin_client.put("/api/v1/admin/system-settings/some_key", json={"value": "a", "value_type": "string"})
    await admin_client.put("/api/v1/admin/system-settings/some_key", json={"value": "b", "value_type": "string"})

    log = await admin_client.get("/api/v1/admin/audit-log", params={"action": "system_setting.upsert"})
    entries = log.json()
    assert len(entries) == 2
    assert entries[0]["after"]["value"] == "b"
    assert entries[0]["before"]["value"] == "a"
