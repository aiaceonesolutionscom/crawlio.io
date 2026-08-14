async def test_list_integrations_returns_catalog(admin_client):
    resp = await admin_client.get("/api/v1/admin/integrations")
    assert resp.status_code == 200
    body = resp.json()
    keys = {item["key"] for item in body}
    assert {"brevo_api_key", "mistral_api_key", "google_client_id"} <= keys
    for item in body:
        assert set(item) >= {
            "key", "label", "description", "env_name", "configured", "source", "masked_value"
        }
        assert item["source"] in {"override", "env", "unset"}
        # Secrets are masked (contain the ellipsis marker); non-secret values
        # (e.g. google_redirect_uri) are shown as-is since they aren't secrets.
        if item["env_name"] == "GOOGLE_REDIRECT_URI":
            assert item["masked_value"] == "—" or item["masked_value"].startswith("http")
        else:
            assert "••••" in item["masked_value"] or item["masked_value"] == "—"


async def test_set_and_clear_override(admin_client):
    resp = await admin_client.put(
        "/api/v1/admin/integrations/mistral_api_key", json={"value": "super-secret-key"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "override"
    assert body["configured"] is True
    assert "super-secret-key" not in body["masked_value"]
    assert "••••" in body["masked_value"]

    listed = await admin_client.get("/api/v1/admin/integrations")
    mistral = next(item for item in listed.json() if item["key"] == "mistral_api_key")
    assert mistral["source"] == "override"

    cleared = await admin_client.delete("/api/v1/admin/integrations/mistral_api_key")
    assert cleared.status_code == 200
    assert cleared.json()["source"] in {"env", "unset"}


async def test_unknown_integration_404(admin_client):
    resp = await admin_client.put("/api/v1/admin/integrations/nope_key", json={"value": "x"})
    assert resp.status_code == 404
    deleted = await admin_client.delete("/api/v1/admin/integrations/nope_key")
    assert deleted.status_code == 404


async def test_test_integration_reports_result_without_live_call(admin_client):
    # The runtime override cache starts empty in the test env, so the test
    # falls through to whatever .env key is present — the point is that the
    # endpoint returns a well-formed ok/message pair without crashing, and the
    # result is truthful either way (a live 401 vs a "not configured").
    resp = await admin_client.post("/api/v1/admin/integrations/brevo_api_key/test")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"ok", "message"}
    assert isinstance(body["ok"], bool)
    assert body["message"]


async def test_override_records_audit_trail(admin_client):
    await admin_client.put("/api/v1/admin/integrations/tavily_api_key", json={"value": "tvly-xyz"})
    log = await admin_client.get("/api/v1/admin/audit-log", params={"action": "integration.override.set"})
    entries = log.json()
    assert len(entries) == 1
    assert entries[0]["target_id"] == "tavily_api_key"
    assert entries[0]["before"] == {"has_override": False}
    assert entries[0]["after"] == {"configured": True, "source": "override"}