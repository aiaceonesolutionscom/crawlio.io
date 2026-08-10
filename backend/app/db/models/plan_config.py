import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlanConfig(Base):
    """Admin-editable replacement for the static dicts in app/core/plans.py."""

    __tablename__ = "plan_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    plan_key: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    lead_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seat_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discovery_result_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_discovery_import_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_email_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
