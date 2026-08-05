import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Sequence(Base):
    __tablename__ = "sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, default="lead_created")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    steps: Mapped[list["SequenceStep"]] = relationship(
        back_populates="sequence", cascade="all, delete-orphan", order_by="SequenceStep.step_order"
    )


class SequenceStep(Base):
    __tablename__ = "sequence_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    sequence_id: Mapped[str] = mapped_column(String(36), ForeignKey("sequences.id"), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    sequence: Mapped["Sequence"] = relationship(back_populates="steps")
