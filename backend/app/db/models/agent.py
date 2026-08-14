import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BusinessProfile(Base):
    """Persistent business information for a workspace's AI agent.
    Set once during onboarding and reused for every outreach/reply/meeting
    so the AI never has to be re-taught the business facts."""

    __tablename__ = "business_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, unique=True, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    business_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    services: Mapped[str] = mapped_column(Text, nullable=False, default="")
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Karachi")
    business_hours: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    knowledge_base: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Meeting(Base):
    """A meeting booked by the AI agent with a lead. Availability is derived
    from the workspace BusinessProfile business_hours + timezone, never invented."""

    __tablename__ = "meetings"
    __table_args__ = (UniqueConstraint("workspace_id", "booking_ref", name="uq_meetings_workspace_ref"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("email_conversations.id"), nullable=True, index=True)
    whatsapp_conversation_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("whatsapp_conversations.id"), nullable=True, index=True)
    booking_ref: Mapped[str] = mapped_column(String(16), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="booked")
    lead_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lead_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lead_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    lead: Mapped["Lead"] = relationship()


class AIActivity(Base):
    """Real-time provenance log of what the AI agent did for a conversation.
    Emitted to the workspace over WebSocket as well as persisted so a paused/
    reloaded client can replay recent activity."""

    __tablename__ = "ai_activity"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("email_conversations.id"), nullable=True, index=True)
    whatsapp_conversation_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("whatsapp_conversations.id"), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="done")  # running | done | failed
    detail: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)