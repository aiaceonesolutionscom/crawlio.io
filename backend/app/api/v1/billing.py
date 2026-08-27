import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.billing_plans import PRO_PRICE_PKR_PAISA, PRO_PRICE_USD_CENTS
from app.core.config import settings
from app.core.deps import get_current_workspace
from app.db.models.workspace import Workspace, WorkspaceMember
from app.db.session import get_session
from app.schemas.billing import CheckoutRequest, CheckoutResponse, SubscriptionRead
from app.services.billing import billing_service, safepay_service, stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


async def _owner_email(session: AsyncSession, workspace_id: str) -> str | None:
    result = await session.execute(
        select(WorkspaceMember.email).where(WorkspaceMember.workspace_id == workspace_id).limit(1)
    )
    return result.scalar_one_or_none()


async def _mock_checkout(
    session: AsyncSession, *, workspace_id: str, plan: str, billing_cycle, provider: str
) -> CheckoutResponse:
    """Staging/demo fallback while a provider's real key isn't set yet: routes
    to an in-app page that looks like a real card-collection checkout but
    always "succeeds", so the rest of the flow (webhook -> active subscription
    -> plan upgrade) can be built and demoed before real API keys exist. The
    moment STRIPE_SECRET_KEY / SAFEPAY_SECRET_KEY is set, create_checkout
    stops calling this path entirely — nothing here is reachable once a
    provider is actually configured (see /mock-checkout/{id}/complete's own
    guard too, for defense in depth)."""
    amount = PRO_PRICE_USD_CENTS[billing_cycle] if provider == "stripe" else PRO_PRICE_PKR_PAISA[billing_cycle]
    currency = "USD" if provider == "stripe" else "PKR"
    checkout_id = f"mock_{uuid.uuid4()}"
    await billing_service.create_pending_subscription(
        session,
        workspace_id=workspace_id,
        provider=provider,
        plan=plan,
        billing_cycle=billing_cycle,
        checkout_id=checkout_id,
        amount_smallest_unit=amount,
        currency=currency,
    )
    checkout_url = (
        f"{settings.frontend_base_url}/billing/mock-checkout/{checkout_id}"
        f"?provider={provider}&cycle={billing_cycle}&amount={amount}&currency={currency}"
    )
    return CheckoutResponse(checkout_url=checkout_url, provider=provider)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: AsyncSession = Depends(get_session),
):
    if not billing_service.is_provider_configured(payload.provider):
        return await _mock_checkout(
            session,
            workspace_id=workspace.id,
            plan=payload.plan,
            billing_cycle=payload.billing_cycle,
            provider=payload.provider,
        )

    if payload.provider == "stripe":
        owner_email = await _owner_email(session, workspace.id)
        checkout = stripe_service.create_checkout_session(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            plan=payload.plan,
            billing_cycle=payload.billing_cycle,
            customer_email=owner_email,
        )
        await billing_service.create_pending_subscription(
            session,
            workspace_id=workspace.id,
            provider="stripe",
            plan=payload.plan,
            billing_cycle=payload.billing_cycle,
            checkout_id=checkout.id,
            amount_smallest_unit=PRO_PRICE_USD_CENTS[payload.billing_cycle],
            currency="USD",
        )
        return CheckoutResponse(checkout_url=checkout.url, provider="stripe")

    # provider == "safepay"
    order = await safepay_service.create_order(
        plan=payload.plan, billing_cycle=payload.billing_cycle, workspace_id=workspace.id
    )
    tracker_token = order.get("data", {}).get("token")
    if not tracker_token:
        logger.error("Safepay order/v1/init returned no tracker token: %s", order)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment provider error — try again.")

    await billing_service.create_pending_subscription(
        session,
        workspace_id=workspace.id,
        provider="safepay",
        plan=payload.plan,
        billing_cycle=payload.billing_cycle,
        checkout_id=tracker_token,
        amount_smallest_unit=PRO_PRICE_PKR_PAISA[payload.billing_cycle],
        currency="PKR",
    )
    return CheckoutResponse(checkout_url=safepay_service.checkout_url(tracker_token), provider="safepay")


@router.post("/mock-checkout/{checkout_id}/complete", response_model=SubscriptionRead)
async def complete_mock_checkout(
    checkout_id: str,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: AsyncSession = Depends(get_session),
):
    """Simulates the provider's webhook for a mock checkout — see
    `_mock_checkout` above. Only ever activates a subscription that (a)
    belongs to the caller's own workspace and (b) is on a provider that's
    still genuinely unconfigured, so this can never be used to skip a real
    payment once live keys are set."""
    subscription = await billing_service.get_subscription_by_checkout_id(session, checkout_id)
    if subscription is None or subscription.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checkout not found")
    if billing_service.is_provider_configured(subscription.provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This provider is now live — use the real checkout instead.",
        )
    if subscription.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Checkout already completed")

    updated = await billing_service.activate_subscription(
        session,
        subscription,
        provider_subscription_id=f"{subscription.provider}_mock_{uuid.uuid4()}",
        provider_customer_id=None,
        current_period_end=billing_service.mock_period_end(subscription.billing_cycle),
    )
    return SubscriptionRead.model_validate(updated)


@router.get("/subscription", response_model=SubscriptionRead | None)
async def get_subscription(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: AsyncSession = Depends(get_session),
):
    subscription = await billing_service.get_active_subscription(session, workspace.id)
    return SubscriptionRead.model_validate(subscription) if subscription else None


@router.post("/cancel")
async def cancel_subscription(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: AsyncSession = Depends(get_session),
):
    canceled = await billing_service.cancel_active_subscription(session, workspace)
    if not canceled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription")
    return {"status": "canceled"}


# --- Webhooks: public, unauthenticated (no workspace/user session exists on a
# server-to-server callback) — trust is established purely via signature
# verification against the raw request body, never by a bearer token. ---


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.construct_webhook_event(payload, sig_header)
    except stripe_service.BillingNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:  # invalid signature/payload — never trust it
        logger.warning("Rejected Stripe webhook: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        subscription = await billing_service.get_subscription_by_checkout_id(session, data["id"])
        if subscription is None:
            logger.warning("Stripe checkout.session.completed for unknown checkout id %s", data["id"])
            return {"status": "ignored"}
        period_end = None
        # The subscription object's period end isn't on the checkout session
        # itself; leave it for the subscription.updated event to fill in.
        await billing_service.activate_subscription(
            session,
            subscription,
            provider_subscription_id=data.get("subscription"),
            provider_customer_id=data.get("customer"),
            current_period_end=period_end,
        )

    elif event_type == "customer.subscription.updated":
        subscription = await billing_service.get_subscription_by_provider_subscription_id(session, data["id"])
        if subscription is not None:
            subscription.current_period_end = datetime.fromtimestamp(data["current_period_end"], tz=timezone.utc)
            await session.commit()

    elif event_type == "customer.subscription.deleted":
        subscription = await billing_service.get_subscription_by_provider_subscription_id(session, data["id"])
        if subscription is not None:
            await billing_service.mark_subscription_canceled(session, subscription)
            await billing_service.downgrade_to_free(session, subscription.workspace_id)

    return {"status": "ok"}


@router.post("/webhooks/safepay", include_in_schema=False)
async def safepay_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    payload = await request.body()
    signature = request.headers.get("x-sfpy-signature")
    if not safepay_service.verify_webhook_signature(payload, signature):
        logger.warning("Rejected Safepay webhook: bad signature")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    body = await request.json()
    # TODO(verify): exact event/status field names once a real Safepay
    # sandbox account exists to inspect an actual webhook payload against.
    tracker_token = body.get("tracker") or body.get("order_id") or body.get("data", {}).get("token")
    payment_state = (body.get("state") or body.get("status") or "").upper()

    if not tracker_token:
        logger.warning("Safepay webhook missing tracker/order id: %s", body)
        return {"status": "ignored"}

    subscription = await billing_service.get_subscription_by_checkout_id(session, tracker_token)
    if subscription is None:
        logger.warning("Safepay webhook for unknown checkout id %s", tracker_token)
        return {"status": "ignored"}

    if payment_state in {"TRACKER_ENDED", "PAID", "SUCCEEDED", "COMPLETED"}:
        await billing_service.activate_subscription(
            session,
            subscription,
            provider_subscription_id=tracker_token,
            provider_customer_id=body.get("user"),
            current_period_end=None,
        )

    return {"status": "ok"}
