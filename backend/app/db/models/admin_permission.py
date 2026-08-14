import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminPermission(Base):
    """A single permission grant for a Sub Admin. Super Admins never need rows
    here — they implicitly hold every permission from the catalog."""

    __tablename__ = "admin_permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("platform_admins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    granted_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("admin_id", "permission", name="uq_admin_permission"),
    )