import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Subscription(Base):
    """One row per checkout attempt/subscription lifecycle for a workspace.
    A workspace can have multiple rows over time (e.g. a canceled sub
    followed by a new one) — `status` on the most recent row is what's
    active; historical rows are kept for the billing history view.
    """

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # "stripe" | "safepay"
    plan: Mapped[str] = mapped_column(String(20), nullable=False)  # "pro" (only self-serve plan today)
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False)  # "monthly" | "yearly"
    # "pending" (checkout created, not yet paid) -> "active" -> "canceled" | "past_due" | "expired"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    provider_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    # Stripe Checkout Session id / Safepay order tracker — set at checkout
    # creation so the webhook (which only knows this id) can find the row.
    provider_checkout_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    amount_smallest_unit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
