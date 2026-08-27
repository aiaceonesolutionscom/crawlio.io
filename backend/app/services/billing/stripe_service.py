"""Stripe Checkout (subscription mode) for the Pro plan — international
cards. Prices are passed inline via `price_data` on each checkout session
rather than pre-created Stripe Price objects, so there's nothing to set up
in the Stripe dashboard beyond an account + API keys.

Keys are read through app.core.integration_runtime.api_key so a key set from
the admin Integrations page takes effect immediately, with no restart — same
mechanism as Brevo/Mistral/Tavily.
"""
import logging
from typing import Optional

import stripe

from app.core.billing_plans import PRO_PRICE_USD_CENTS, BillingCycle
from app.core.config import settings
from app.core.integration_runtime import api_key as _api_key

logger = logging.getLogger(__name__)

_STRIPE_INTERVAL: dict[BillingCycle, str] = {"monthly": "month", "yearly": "year"}


class BillingNotConfiguredError(Exception):
    """Raised when a checkout is attempted before a Stripe secret key is set."""


def _client() -> None:
    key = _api_key("stripe_secret_key")
    if not key:
        raise BillingNotConfiguredError("Stripe is not configured (set it in Admin -> Integrations).")
    stripe.api_key = key


def create_checkout_session(
    *, workspace_id: str, workspace_name: str, plan: str, billing_cycle: BillingCycle, customer_email: Optional[str]
) -> stripe.checkout.Session:
    """Creates a Stripe Checkout Session in subscription mode. Raises
    BillingNotConfiguredError if Stripe keys aren't set — callers should turn
    that into a clear 503 rather than a raw 500."""
    _client()
    amount_cents = PRO_PRICE_USD_CENTS[billing_cycle]
    return stripe.checkout.Session.create(
        mode="subscription",
        client_reference_id=workspace_id,
        customer_email=customer_email,
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount_cents,
                    "recurring": {"interval": _STRIPE_INTERVAL[billing_cycle]},
                    "product_data": {
                        "name": f"Crawlio {plan.capitalize()} — {billing_cycle}",
                        "description": f"Crawlio {plan.capitalize()} plan for {workspace_name}",
                    },
                },
                "quantity": 1,
            }
        ],
        success_url=f"{settings.billing_success_url}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=settings.billing_cancel_url,
        metadata={"workspace_id": workspace_id, "plan": plan, "billing_cycle": billing_cycle},
        subscription_data={"metadata": {"workspace_id": workspace_id, "plan": plan, "billing_cycle": billing_cycle}},
    )


def cancel_subscription(provider_subscription_id: str) -> None:
    """Cancels at period end — the workspace keeps Pro access until the
    current billing period actually ends, matching the existing "downgrades
    apply at the end of the cycle" messaging already shown in the app."""
    _client()
    try:
        stripe.Subscription.modify(provider_subscription_id, cancel_at_period_end=True)
    except stripe.error.InvalidRequestError as exc:
        logger.warning("Stripe cancel failed for %s: %s", provider_subscription_id, exc)


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    webhook_secret = _api_key("stripe_webhook_secret")
    if not webhook_secret:
        raise BillingNotConfiguredError("Stripe webhook secret is not configured.")
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
