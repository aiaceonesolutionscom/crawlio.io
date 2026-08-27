import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.billing_plans import BillingCycle
from app.core.integration_runtime import api_key as _api_key
from app.db.models.subscription import Subscription
from app.db.models.workspace import Workspace
from app.services.billing import safepay_service, stripe_service
from app.services.workspace import workspace_service

logger = logging.getLogger(__name__)


def is_provider_configured(provider: str) -> bool:
    if provider == "stripe":
        return bool(_api_key("stripe_secret_key"))
    if provider == "safepay":
        return bool(_api_key("safepay_secret_key"))
    return False


def mock_period_end(billing_cycle: BillingCycle) -> datetime:
    days = 30 if billing_cycle == "monthly" else 365
    return datetime.now(timezone.utc) + timedelta(days=days)


async def get_active_subscription(session: AsyncSession, workspace_id: str) -> Optional[Subscription]:
    result = await session.execute(
        select(Subscription)
        .where(Subscription.workspace_id == workspace_id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().first()


async def get_subscription_by_checkout_id(session: AsyncSession, checkout_id: str) -> Optional[Subscription]:
    result = await session.execute(select(Subscription).where(Subscription.provider_checkout_id == checkout_id))
    return result.scalar_one_or_none()


async def get_active_subscriptions_for_workspaces(
    session: AsyncSession, workspace_ids: list[str]
) -> dict[str, Subscription]:
    """Batch lookup for the admin workspaces list — one query instead of one
    per row. Newest-active wins per workspace if somehow more than one row is
    "active" at once (shouldn't happen, but never crash the admin list over it)."""
    if not workspace_ids:
        return {}
    result = await session.execute(
        select(Subscription)
        .where(Subscription.workspace_id.in_(workspace_ids), Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
    )
    by_workspace: dict[str, Subscription] = {}
    for sub in result.scalars().all():
        by_workspace.setdefault(sub.workspace_id, sub)
    return by_workspace


async def get_subscription_by_provider_subscription_id(
    session: AsyncSession, provider_subscription_id: str
) -> Optional[Subscription]:
    result = await session.execute(
        select(Subscription).where(Subscription.provider_subscription_id == provider_subscription_id)
    )
    return result.scalar_one_or_none()


async def create_pending_subscription(
    session: AsyncSession,
    *,
    workspace_id: str,
    provider: str,
    plan: str,
    billing_cycle: BillingCycle,
    checkout_id: str,
    amount_smallest_unit: int,
    currency: str,
) -> Subscription:
    sub = Subscription(
        workspace_id=workspace_id,
        provider=provider,
        plan=plan,
        billing_cycle=billing_cycle,
        status="pending",
        provider_checkout_id=checkout_id,
        amount_smallest_unit=amount_smallest_unit,
        currency=currency,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


async def activate_subscription(
    session: AsyncSession,
    subscription: Subscription,
    *,
    provider_subscription_id: Optional[str],
    provider_customer_id: Optional[str],
    current_period_end: Optional[datetime],
) -> Subscription:
    """Marks a subscription active and upgrades the workspace's plan — called
    once a webhook confirms payment actually succeeded, never at checkout
    creation time (a created checkout session isn't a paid one)."""
    subscription.status = "active"
    subscription.provider_subscription_id = provider_subscription_id
    subscription.provider_customer_id = provider_customer_id
    subscription.current_period_end = current_period_end
    await session.commit()
    await session.refresh(subscription)

    workspace_result = await session.execute(select(Workspace).where(Workspace.id == subscription.workspace_id))
    workspace = workspace_result.scalar_one_or_none()
    if workspace is not None:
        await workspace_service.change_plan(session, workspace, subscription.plan)
    else:
        logger.error("Subscription %s activated for missing workspace %s", subscription.id, subscription.workspace_id)
    return subscription


async def mark_subscription_canceled(session: AsyncSession, subscription: Subscription) -> None:
    subscription.status = "canceled"
    subscription.canceled_at = datetime.now(timezone.utc)
    await session.commit()


async def downgrade_to_free(session: AsyncSession, workspace_id: str) -> None:
    """Called when a subscription actually ends (Stripe's
    customer.subscription.deleted, fired at period end for a
    cancel_at_period_end sub) — moves the workspace back to Free."""
    result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is not None:
        await workspace_service.change_plan(session, workspace, "free")


async def cancel_active_subscription(session: AsyncSession, workspace: Workspace) -> bool:
    """Requests cancellation with the provider (access continues until the
    current period ends) and marks the row canceled. Returns False if there's
    no active subscription to cancel."""
    subscription = await get_active_subscription(session, workspace.id)
    if subscription is None:
        return False

    if subscription.provider == "stripe" and subscription.provider_subscription_id:
        stripe_service.cancel_subscription(subscription.provider_subscription_id)
    elif subscription.provider == "safepay":
        # Safepay checkout here is a one-time charge per cycle, not a native
        # recurring subscription object to cancel with them — cancellation is
        # purely local: no future charge gets initiated for this workspace.
        pass

    await mark_subscription_canceled(session, subscription)
    return True
