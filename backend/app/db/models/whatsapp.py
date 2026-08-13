import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WhatsAppAccount(Base):
    """A workspace's connected WhatsApp Business number (Cloud API).

    Mirrors EmailAccount: one row per connected number, tokens stored so the
    user connects once and never has to re-auth. Tokens are permanent
    (Embedded Signup / System User with Expire=Never) — reconnection is only
    ever needed when the user revokes the app in Meta themselves."""

    __tablename__ = "whatsapp_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone_number_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    waba_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    business_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_type: Mapped[str] = mapped_column(String(20), nullable=False, default="system_user")  # embedded_signup | system_user
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    conversations: Mapped[list["WhatsAppConversation"]] = relationship(
        back_populates="whatsapp_account", cascade="all, delete-orphan"
    )


class WhatsAppConversation(Base):
    """One stable conversation per customer phone number, exactly like
    EmailConversation. The AI agent answers inbound within the 24h session
    window; users can take over manually anytime."""

    __tablename__ = "whatsapp_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    whatsapp_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("whatsapp_accounts.id"), nullable=False, index=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("leads.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    ai_agent_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    business_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_processed_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    whatsapp_account: Mapped["WhatsAppAccount"] = relationship(back_populates="conversations")
    messages: Mapped[list["WhatsAppConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class WhatsAppConversationMessage(Base):
    """A single WhatsApp message in a conversation. provider_message_id is the
    Meta wamid — the dedup key so a webhook delivery is never processed twice."""

    __tablename__ = "whatsapp_conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("whatsapp_conversations.id"), nullable=False, index=True)
    sender_type: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="inbound")
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    conversation: Mapped["WhatsAppConversation"] = relationship(back_populates="messages")


class WhatsAppTemplate(Base):
    """Approved message templates for business-initiated (outreach) messages.
    Meta policy: outbound to a customer outside the 24h session window must use
    an approved template. The AI drafts the body; the system submits it and
    sends once Meta marks it APPROVED."""

    __tablename__ = "whatsapp_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    waba_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list of param names
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | approved | rejected
    meta_template_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
