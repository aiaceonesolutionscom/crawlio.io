import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import respx
from httpx import Response

from app.core import integration_runtime
from app.core.config import settings
from app.services.billing import billing_service, safepay_service, stripe_service


@pytest.fixture(autouse=True)
def _reset_billing_settings(monkeypatch):
    """Billing settings default to empty/unconfigured — tests opt in per-case
    via monkeypatch so "not configured" is the safe default everywhere else.
    Also clears any admin-panel override so one test's `set_override` call
    can't leak into the next (the cache is process-global, not per-test)."""
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    monkeypatch.setattr(settings, "safepay_secret_key", "")
    monkeypatch.setattr(settings, "safepay_webhook_secret", "sfpy_test_secret")
    monkeypatch.setattr(settings, "safepay_beacon_key", "beacon_test")
    integration_runtime.clear_override("stripe_secret_key")
    integration_runtime.clear_override("safepay_secret_key")
    yield
    integration_runtime.clear_override("stripe_secret_key")
    integration_runtime.clear_override("safepay_secret_key")


async def _create_workspace(authed_client):
    resp = await authed_client.post("/api/v1/workspaces", json={"name": "Acme"})
    assert resp.status_code == 201
    return resp.json()


async def test_checkout_stripe_falls_back_to_mock_when_not_configured(authed_client):
    await _create_workspace(authed_client)
    resp = await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "monthly", "provider": "stripe"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "stripe"
    assert "/billing/mock-checkout/" in body["checkout_url"]


async def test_checkout_safepay_falls_back_to_mock_when_not_configured(authed_client):
    await _create_workspace(authed_client)
    resp = await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "monthly", "provider": "safepay"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "safepay"
    assert "/billing/mock-checkout/" in body["checkout_url"]


async def test_mock_checkout_completes_and_upgrades_plan(authed_client):
    workspace = await _create_workspace(authed_client)
    assert workspace["plan"] == "free"

    checkout_resp = await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "yearly", "provider": "stripe"}
    )
    checkout_url = checkout_resp.json()["checkout_url"]
    checkout_id = checkout_url.split("/billing/mock-checkout/")[1].split("?")[0]

    complete_resp = await authed_client.post(f"/api/v1/billing/mock-checkout/{checkout_id}/complete")
    assert complete_resp.status_code == 200
    body = complete_resp.json()
    assert body["status"] == "active"
    assert body["billing_cycle"] == "yearly"

    ws_resp = await authed_client.get("/api/v1/workspaces/me")
    assert ws_resp.json()["plan"] == "pro"


async def test_mock_checkout_cannot_double_complete(authed_client):
    await _create_workspace(authed_client)
    checkout_resp = await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "monthly", "provider": "stripe"}
    )
    checkout_id = checkout_resp.json()["checkout_url"].split("/billing/mock-checkout/")[1].split("?")[0]

    first = await authed_client.post(f"/api/v1/billing/mock-checkout/{checkout_id}/complete")
    assert first.status_code == 200
    second = await authed_client.post(f"/api/v1/billing/mock-checkout/{checkout_id}/complete")
    assert second.status_code == 400


async def test_mock_checkout_refuses_once_provider_is_configured(authed_client, monkeypatch):
    await _create_workspace(authed_client)
    checkout_resp = await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "monthly", "provider": "stripe"}
    )
    checkout_id = checkout_resp.json()["checkout_url"].split("/billing/mock-checkout/")[1].split("?")[0]

    # Real key shows up later (founder finishes staging) — the mock path for
    # this already-pending checkout must not silently activate anymore.
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_live_now_real")
    resp = await authed_client.post(f"/api/v1/billing/mock-checkout/{checkout_id}/complete")
    assert resp.status_code == 400


async def test_mock_checkout_rejects_other_workspaces_checkout(client_factory):
    async with client_factory("user_a") as client_a:
        await client_a.post("/api/v1/workspaces", json={"name": "Workspace A"})
        checkout_resp = await client_a.post(
            "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "monthly", "provider": "stripe"}
        )
    checkout_id = checkout_resp.json()["checkout_url"].split("/billing/mock-checkout/")[1].split("?")[0]

    async with client_factory("user_b") as client_b:
        await client_b.post("/api/v1/workspaces", json={"name": "Workspace B"})
        resp = await client_b.post(f"/api/v1/billing/mock-checkout/{checkout_id}/complete")
    assert resp.status_code == 404


async def test_get_subscription_returns_null_when_none_exists(authed_client):
    await _create_workspace(authed_client)
    resp = await authed_client.get("/api/v1/billing/subscription")
    assert resp.status_code == 200
    assert resp.json() is None


async def test_cancel_returns_404_when_no_active_subscription(authed_client):
    await _create_workspace(authed_client)
    resp = await authed_client.post("/api/v1/billing/cancel")
    assert resp.status_code == 404


async def test_checkout_stripe_creates_pending_subscription(authed_client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    workspace = await _create_workspace(authed_client)

    fake_session = SimpleNamespace(id="cs_test_123", url="https://checkout.stripe.com/pay/cs_test_123")
    monkeypatch.setattr(stripe_service.stripe.checkout.Session, "create", lambda **kwargs: fake_session)

    resp = await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "yearly", "provider": "stripe"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"checkout_url": fake_session.url, "provider": "stripe"}

    sub_resp = await authed_client.get("/api/v1/billing/subscription")
    # Still pending (no webhook fired yet) — not surfaced as "active" to the UI.
    assert sub_resp.json() is None


async def test_stripe_webhook_activates_subscription_and_upgrades_plan(authed_client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")
    workspace = await _create_workspace(authed_client)
    assert workspace["plan"] == "free"

    fake_session = SimpleNamespace(id="cs_test_456", url="https://checkout.stripe.com/pay/cs_test_456")
    monkeypatch.setattr(stripe_service.stripe.checkout.Session, "create", lambda **kwargs: fake_session)
    checkout_resp = await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "monthly", "provider": "stripe"}
    )
    assert checkout_resp.status_code == 200

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_456", "subscription": "sub_test_1", "customer": "cus_test_1"}},
    }
    monkeypatch.setattr(stripe_service, "construct_webhook_event", lambda payload, sig: event)

    webhook_resp = await authed_client.post(
        "/api/v1/billing/webhooks/stripe",
        content=json.dumps(event),
        headers={"stripe-signature": "fake"},
    )
    assert webhook_resp.status_code == 200

    sub_resp = await authed_client.get("/api/v1/billing/subscription")
    body = sub_resp.json()
    assert body is not None
    assert body["status"] == "active"
    assert body["provider"] == "stripe"

    ws_resp = await authed_client.get("/api/v1/workspaces/me")
    assert ws_resp.json()["plan"] == "pro"


async def test_stripe_webhook_rejects_bad_signature(authed_client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")

    def _raise(*args, **kwargs):
        raise ValueError("bad signature")

    monkeypatch.setattr(stripe_service, "construct_webhook_event", _raise)
    resp = await authed_client.post(
        "/api/v1/billing/webhooks/stripe", content=b"{}", headers={"stripe-signature": "bad"}
    )
    assert resp.status_code == 400


async def test_safepay_webhook_signature_verification():
    payload = b'{"tracker": "trk_123", "state": "PAID"}'
    good_sig = safepay_service.verify_webhook_signature(
        payload,
        __import__("hmac")
        .new(b"sfpy_test_secret", payload, __import__("hashlib").sha256)
        .hexdigest(),
    )
    assert good_sig is True
    assert safepay_service.verify_webhook_signature(payload, "wrong-signature") is False
    assert safepay_service.verify_webhook_signature(payload, None) is False


async def test_safepay_checkout_creates_pending_subscription_and_redirects(authed_client, monkeypatch):
    monkeypatch.setattr(settings, "safepay_secret_key", "sec_fake")
    await _create_workspace(authed_client)

    with respx.mock:
        respx.post("https://sandbox.api.getsafepay.com/order/v1/init").mock(
            return_value=Response(200, json={"data": {"token": "trk_fake_1"}})
        )
        resp = await authed_client.post(
            "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "monthly", "provider": "safepay"}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "safepay"
    assert "trk_fake_1" in body["checkout_url"]
    assert "beacon=beacon_test" in body["checkout_url"]


async def test_cancel_stripe_subscription_marks_canceled(authed_client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")
    await _create_workspace(authed_client)

    fake_session = SimpleNamespace(id="cs_test_789", url="https://checkout.stripe.com/pay/cs_test_789")
    monkeypatch.setattr(stripe_service.stripe.checkout.Session, "create", lambda **kwargs: fake_session)
    await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "monthly", "provider": "stripe"}
    )
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_789", "subscription": "sub_test_2", "customer": "cus_test_2"}},
    }
    monkeypatch.setattr(stripe_service, "construct_webhook_event", lambda payload, sig: event)
    await authed_client.post(
        "/api/v1/billing/webhooks/stripe", content=json.dumps(event), headers={"stripe-signature": "fake"}
    )

    monkeypatch.setattr(stripe_service, "cancel_subscription", lambda sub_id: None)
    cancel_resp = await authed_client.post("/api/v1/billing/cancel")
    assert cancel_resp.status_code == 200

    sub_resp = await authed_client.get("/api/v1/billing/subscription")
    # Canceled subs aren't "active" anymore — endpoint returns null, matching
    # the "no active subscription" contract get_subscription documents.
    assert sub_resp.json() is None


async def test_admin_set_stripe_key_unblocks_real_checkout_immediately(authed_client, admin_client, monkeypatch):
    """The whole point of reading keys through integration_runtime: an admin
    setting the key from the panel must flip checkout from mock to real with
    no restart, in the same running process."""
    await _create_workspace(authed_client)
    mock_resp = await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "monthly", "provider": "stripe"}
    )
    assert "/billing/mock-checkout/" in mock_resp.json()["checkout_url"]

    set_resp = await admin_client.put(
        "/api/v1/admin/integrations/stripe_secret_key", json={"value": "sk_test_admin_set"}
    )
    assert set_resp.status_code == 200

    fake_session = SimpleNamespace(id="cs_test_admin", url="https://checkout.stripe.com/pay/cs_test_admin")
    monkeypatch.setattr(stripe_service.stripe.checkout.Session, "create", lambda **kwargs: fake_session)

    real_resp = await authed_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro", "billing_cycle": "monthly", "provider": "stripe"}
    )
    assert real_resp.json() == {"checkout_url": fake_session.url, "provider": "stripe"}
