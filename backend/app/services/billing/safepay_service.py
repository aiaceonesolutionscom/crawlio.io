"""Safepay checkout — Pakistan-local cards + JazzCash/EasyPaisa, for the Pro
plan. Built from Safepay's public API reference (apidocs.getsafepay.com) and
their official PHP SDK (github.com/getsafepay/sfpy-php); this integration has
NOT been exercised against a real Safepay sandbox account yet (no API keys
were available while building it), so treat the request/response field names
and the checkout redirect URL as needing a real end-to-end smoke test the
first time SAFEPAY_SECRET_KEY is actually set — see TODO(verify) markers
below for the specific spots most likely to need adjustment.

Flow: POST /order/v1/init creates an order and returns a `token` (the
"tracker") -> redirect the customer to Safepay's hosted checkout with that
tracker -> Safepay POSTs a signed webhook back to us on payment completion.
Unlike Stripe, this charges once per billing cycle rather than using a native
recurring-subscription object — renewal is driven by our own reminder/charge
flow, not Safepay auto-billing.
"""
import hashlib
import hmac
import logging
from typing import Optional

import httpx

from app.core.billing_plans import PRO_PRICE_PKR_PAISA, BillingCycle
from app.core.config import settings
from app.core.integration_runtime import api_key as _api_key

logger = logging.getLogger(__name__)

_BASE_URLS = {
    "sandbox": "https://sandbox.api.getsafepay.com",
    "production": "https://api.getsafepay.com",
}
# TODO(verify): confirm this is still the correct hosted-checkout host once a
# real sandbox account exists — the checkout domain has historically been
# separate from the api.* host (e.g. sandbox.getsafepay.com).
_CHECKOUT_HOSTS = {
    "sandbox": "https://sandbox.getsafepay.com",
    "production": "https://getsafepay.com",
}


class BillingNotConfiguredError(Exception):
    pass


def _require_configured() -> str:
    key = _api_key("safepay_secret_key")
    if not key:
        raise BillingNotConfiguredError("Safepay is not configured (set it in Admin -> Integrations).")
    return key


async def create_order(*, plan: str, billing_cycle: BillingCycle, workspace_id: str) -> dict:
    """Creates a Safepay order and returns the raw response body (contains
    `data.token`, the tracker used to build the checkout redirect URL)."""
    secret_key = _require_configured()
    amount = PRO_PRICE_PKR_PAISA[billing_cycle]
    base_url = _BASE_URLS[settings.safepay_environment]
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{base_url}/order/v1/init",
            headers={"Content-Type": "application/json"},
            json={
                # TODO(verify): the API reference and the PHP SDK disagree on
                # this field's name ("client" vs "merchant_api_key") — using
                # the PHP SDK's name since it's a working, versioned example.
                "merchant_api_key": secret_key,
                "intent": "CYBERSOURCE",
                "mode": "payment",
                "currency": "PKR",
                "amount": amount,
                "metadata": {"workspace_id": workspace_id, "plan": plan, "billing_cycle": billing_cycle},
            },
        )
        resp.raise_for_status()
        return resp.json()


def checkout_url(tracker_token: str) -> str:
    host = _CHECKOUT_HOSTS[settings.safepay_environment]
    params = {
        "env": settings.safepay_environment,
        "beacon": _api_key("safepay_beacon_key"),
        "source": "custom",
        "order_id": tracker_token,
        "redirect_url": settings.billing_success_url,
        "cancel_url": settings.billing_cancel_url,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{host}/checkout/pay?{query}"


def verify_webhook_signature(payload: bytes, signature: Optional[str]) -> bool:
    """HMAC-SHA256 of the raw request body against the Safepay webhook secret.
    TODO(verify): confirm this matches Safepay's actual signing scheme (the
    PHP SDK's Webhook::constructEvent wraps this but its internals weren't
    visible from the docs fetched while building this) before relying on it
    to gate real payment confirmations."""
    webhook_secret = _api_key("safepay_webhook_secret")
    if not signature or not webhook_secret:
        return False
    expected = hmac.new(webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
