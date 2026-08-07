import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CrmEntry(Base):
    """A lead the user has explicitly promoted into the CRM (from the AI lead
    filter) — a separate list from the general Leads table, feeding the CRM
    box on the Automation page."""

    __tablename__ = "crm_entries"
    __table_args__ = (UniqueConstraint("workspace_id", "lead_id", name="uq_crm_entries_workspace_lead"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # "with_website" | "no_website"
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    lead: Mapped["Lead"] = relationship()
