import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.permissions import ROLE_SUPER_ADMIN
from app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    # super_admin has every permission; sub_admin only what is explicitly granted
    # in admin_permissions. Defaults to super_admin for backwards compatibility.
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_SUPER_ADMIN)
    # Clerk's `sub` claim. NULL until this admin's first authenticated request lazy-binds it.
    clerk_user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    added_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
