"""business profiles, meetings, ai activity, lead outreach columns

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-08-10 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("business_name", sa.String(length=255), nullable=False),
        sa.Column("owner_name", sa.String(length=255), nullable=False),
        sa.Column("business_phone", sa.String(length=50), nullable=True),
        sa.Column("business_address", sa.String(length=500), nullable=True),
        sa.Column("services", sa.Text, nullable=False),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Karachi"),
        sa.Column("business_hours", sa.JSON, nullable=False),
        sa.Column("knowledge_base", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_business_profiles_workspace"),
    )
    op.create_index(op.f("ix_business_profiles_workspace_id"), "business_profiles", ["workspace_id"], unique=True)

    op.create_table(
        "meetings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("booking_ref", sa.String(length=16), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="booked"),
        sa.Column("lead_name", sa.String(length=255), nullable=True),
        sa.Column("lead_email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["email_conversations.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "booking_ref", name="uq_meetings_workspace_ref"),
    )
    op.create_index(op.f("ix_meetings_workspace_id"), "meetings", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_meetings_lead_id"), "meetings", ["lead_id"], unique=False)
    op.create_index(op.f("ix_meetings_conversation_id"), "meetings", ["conversation_id"], unique=False)

    op.create_table(
        "ai_activity",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="done"),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["email_conversations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_activity_workspace_id"), "ai_activity", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_ai_activity_conversation_id"), "ai_activity", ["conversation_id"], unique=False)

    op.add_column("leads", sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("outreach_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_leads_unsubscribed_at"), "leads", ["unsubscribed_at"], unique=False)
    op.create_index(op.f("ix_leads_outreach_sent_at"), "leads", ["outreach_sent_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_leads_outreach_sent_at"), table_name="leads")
    op.drop_index(op.f("ix_leads_unsubscribed_at"), table_name="leads")
    op.drop_column("leads", "outreach_sent_at")
    op.drop_column("leads", "unsubscribed_at")

    op.drop_index(op.f("ix_ai_activity_conversation_id"), table_name="ai_activity")
    op.drop_index(op.f("ix_ai_activity_workspace_id"), table_name="ai_activity")
    op.drop_table("ai_activity")

    op.drop_index(op.f("ix_meetings_conversation_id"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_lead_id"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_workspace_id"), table_name="meetings")
    op.drop_table("meetings")

    op.drop_index(op.f("ix_business_profiles_workspace_id"), table_name="business_profiles")
    op.drop_table("business_profiles")