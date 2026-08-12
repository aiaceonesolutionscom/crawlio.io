import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiscoveryCache(Base):
    """Shared, global cache of validated lead-discovery results per
    niche+city+country. Deliberately NOT workspace-scoped — this is public
    business-listing data (name/phone/website/etc, already gated through the
    same MX/phone validation as a live search), so every workspace searching
    the same niche+city benefits from one another's prior scrapes instead of
    re-hitting Google Maps/OSM/directories from scratch every time."""

    __tablename__ = "discovery_cache"
    __table_args__ = (
        UniqueConstraint("niche_key", "city_key", "country_code", name="uq_discovery_cache_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    # Normalized/canonical lookup key components.
    niche_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    city_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    # Original display text (whatever the request that populated this row used).
    niche: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(120), nullable=False)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_counts: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
