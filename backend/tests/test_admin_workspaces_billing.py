from types import SimpleNamespace

from app.core.config import settings
from app.services.billing import stripe_service


async def _create_active_pro_subscription(authed_client, monkeypatch):
    """Full real path: checkout -> webhook -> active subscription, so the
    admin view is asserting against the same state a real customer produces,
    not a hand-inserted row."""
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")

    ws_resp = await authed_client.post("/api/v1/workspaces", json={"name": "Billed Co"})
    workspace_id = ws_resp.json()["id"]

    fake_session = SimpleNamespace(id="cs_admin_view", url="https://checkout.stripe.com/pay/cs_admin_view")
    monkeypatch.setattr(stripe_service.stripe.checkout.Session, "create", lambda **kwargs: fake_session)
    await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "yearly", "provider": "stripe"}
    )

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_admin_view", "subscription": "sub_admin_view", "customer": "cus_admin_view"}},
    }
    monkeypatch.setattr(stripe_service, "construct_webhook_event", lambda payload, sig: event)
    import json

    await authed_client.post(
        "/api/v1/billing/webhooks/stripe", content=json.dumps(event), headers={"stripe-signature": "fake"}
    )
    return workspace_id


async def test_admin_workspace_list_shows_subscription(authed_client, admin_client, monkeypatch):
    await _create_active_pro_subscription(authed_client, monkeypatch)

    resp = await admin_client.get("/api/v1/admin/workspaces")
    assert resp.status_code == 200
    rows = resp.json()
    billed = next(r for r in rows if r["name"] == "Billed Co")
    assert billed["subscription"] == {
        "provider": "stripe",
        "status": "active",
        "billing_cycle": "yearly",
        "current_period_end": None,
    }


async def test_admin_workspace_detail_shows_subscription(authed_client, admin_client, monkeypatch):
    workspace_id = await _create_active_pro_subscription(authed_client, monkeypatch)

    resp = await admin_client.get(f"/api/v1/admin/workspaces/{workspace_id}")
    assert resp.status_code == 200
    assert resp.json()["subscription"]["status"] == "active"


async def test_admin_workspace_without_subscription_shows_null(admin_client):
    resp = await admin_client.get("/api/v1/admin/workspaces")
    assert resp.status_code == 200
    for row in resp.json():
        assert row["subscription"] is None
