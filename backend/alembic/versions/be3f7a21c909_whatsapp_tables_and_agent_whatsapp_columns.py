"""whatsapp tables + agent whatsapp columns (schema drift fix)

The WhatsApp feature was shipped without migrations — the 4 WhatsApp tables and
the whatsapp_* columns on leads/meetings/ai_activity existed only in the models
and in the dev SQLite DB (via create_all). A fresh `alembic upgrade head` on
Postgres was missing the entire WhatsApp schema. This migration closes that gap.

Revision ID: be3f7a21c909
Revises: c4d5e6f7a8b9
Create Date: 2026-08-13 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "be3f7a21c909"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade_whatsapp_tables() -> None:
    op.create_table(
        "whatsapp_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("phone_number_id", sa.String(length=64), nullable=False),
        sa.Column("waba_id", sa.String(length=64), nullable=True),
        sa.Column("business_phone", sa.String(length=32), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("daily_sent_count", sa.Integer(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_whatsapp_accounts_workspace"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_accounts_workspace_id", "whatsapp_accounts", ["workspace_id"], unique=False)
    op.create_index("ix_whatsapp_accounts_user_id", "whatsapp_accounts", ["user_id"], unique=False)
    op.create_index("ix_whatsapp_accounts_phone_number_id", "whatsapp_accounts", ["phone_number_id"], unique=False)

    op.create_table(
        "whatsapp_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("whatsapp_account_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("ai_agent_active", sa.Boolean(), nullable=False),
        sa.Column("business_context", sa.Text(), nullable=True),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("last_processed_message_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["whatsapp_account_id"], ["whatsapp_accounts.id"], name="fk_wa_conversations_account"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], name="fk_wa_conversations_lead"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_wa_conversations_workspace"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_conversations_workspace_id", "whatsapp_conversations", ["workspace_id"], unique=False)
    op.create_index("ix_whatsapp_conversations_whatsapp_account_id", "whatsapp_conversations", ["whatsapp_account_id"], unique=False)
    op.create_index("ix_whatsapp_conversations_lead_id", "whatsapp_conversations", ["lead_id"], unique=False)
    op.create_index("ix_whatsapp_conversations_customer_phone", "whatsapp_conversations", ["customer_phone"], unique=False)

    op.create_table(
        "whatsapp_conversation_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("sender_type", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_approved", sa.Boolean(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["whatsapp_conversations.id"], name="fk_wa_messages_conversation"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_conversation_messages_conversation_id", "whatsapp_conversation_messages", ["conversation_id"], unique=False)
    op.create_index("ix_whatsapp_conversation_messages_provider_message_id", "whatsapp_conversation_messages", ["provider_message_id"], unique=False)

    op.create_table(
        "whatsapp_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("waba_id", sa.String(length=64), nullable=True),
        sa.Column("template_name", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("params", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("meta_template_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_wa_templates_workspace"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_templates_workspace_id", "whatsapp_templates", ["workspace_id"], unique=False)


def upgrade_whatsapp_columns() -> None:
    # leads.whatsapp_outreach_sent_at (DT-of-outreach for daily quotas)
    op.add_column("leads", sa.Column("whatsapp_outreach_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_leads_whatsapp_outreach_sent_at", "leads", ["whatsapp_outreach_sent_at"], unique=False)

    # meetings: conversation link + booked lead phone
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.add_column(sa.Column("whatsapp_conversation_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("lead_phone", sa.String(length=32), nullable=True))
        batch_op.create_index("ix_meetings_whatsapp_conversation_id", ["whatsapp_conversation_id"], unique=False)
        batch_op.create_index("ix_meetings_lead_phone", ["lead_phone"], unique=False)
        batch_op.create_foreign_key(
            "fk_meetings_wa_conversation", "whatsapp_conversations", ["whatsapp_conversation_id"], ["id"]
        )

    # ai_activity: whatsapp conversation link
    with op.batch_alter_table("ai_activity") as batch_op:
        batch_op.add_column(sa.Column("whatsapp_conversation_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_ai_activity_whatsapp_conversation_id", ["whatsapp_conversation_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_ai_activity_wa_conversation", "whatsapp_conversations", ["whatsapp_conversation_id"], ["id"]
        )


def downgrade_whatsapp_columns() -> None:
    with op.batch_alter_table("ai_activity") as batch_op:
        batch_op.drop_constraint("fk_ai_activity_wa_conversation", type_="foreignkey")
        batch_op.drop_index("ix_ai_activity_whatsapp_conversation_id")
        batch_op.drop_column("whatsapp_conversation_id")

    with op.batch_alter_table("meetings") as batch_op:
        batch_op.drop_constraint("fk_meetings_wa_conversation", type_="foreignkey")
        batch_op.drop_index("ix_meetings_lead_phone")
        batch_op.drop_index("ix_meetings_whatsapp_conversation_id")
        batch_op.drop_column("lead_phone")
        batch_op.drop_column("whatsapp_conversation_id")

    op.drop_index("ix_leads_whatsapp_outreach_sent_at", table_name="leads")
    op.drop_column("leads", "whatsapp_outreach_sent_at")


def downgrade_whatsapp_tables() -> None:
    op.drop_index("ix_whatsapp_templates_workspace_id", table_name="whatsapp_templates")
    op.drop_table("whatsapp_templates")
    op.drop_index("ix_whatsapp_conversation_messages_provider_message_id", table_name="whatsapp_conversation_messages")
    op.drop_index("ix_whatsapp_conversation_messages_conversation_id", table_name="whatsapp_conversation_messages")
    op.drop_table("whatsapp_conversation_messages")
    op.drop_index("ix_whatsapp_conversations_customer_phone", table_name="whatsapp_conversations")
    op.drop_index("ix_whatsapp_conversations_lead_id", table_name="whatsapp_conversations")
    op.drop_index("ix_whatsapp_conversations_whatsapp_account_id", table_name="whatsapp_conversations")
    op.drop_index("ix_whatsapp_conversations_workspace_id", table_name="whatsapp_conversations")
    op.drop_table("whatsapp_conversations")
    op.drop_index("ix_whatsapp_accounts_phone_number_id", table_name="whatsapp_accounts")
    op.drop_index("ix_whatsapp_accounts_user_id", table_name="whatsapp_accounts")
    op.drop_index("ix_whatsapp_accounts_workspace_id", table_name="whatsapp_accounts")
    op.drop_table("whatsapp_accounts")


def upgrade() -> None:
    upgrade_whatsapp_tables()
    upgrade_whatsapp_columns()


def downgrade() -> None:
    downgrade_whatsapp_columns()
    downgrade_whatsapp_tables()