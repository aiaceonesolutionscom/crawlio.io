"""create email_accounts email_conversations email_conversation_messages email_drafts daily_email_quotas

Revision ID: e1f2g3h4i5j6
Revises: 08c8b54e1fba
Create Date: 2026-08-06 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e1f2g3h4i5j6"
down_revision: Union[str, None] = "08c8b54e1fba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("email_address", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("daily_sent_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_accounts_workspace_id"), "email_accounts", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_email_accounts_user_id"), "email_accounts", ["user_id"], unique=False)

    op.create_table(
        "email_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("email_account_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("ai_agent_active", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("business_context", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["email_account_id"], ["email_accounts.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_conversations_workspace_id"), "email_conversations", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_email_conversations_email_account_id"), "email_conversations", ["email_account_id"], unique=False)
    op.create_index(op.f("ix_email_conversations_lead_id"), "email_conversations", ["lead_id"], unique=False)

    op.create_table(
        "email_conversation_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("sender_type", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_approved", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["email_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_conversation_messages_conversation_id"), "email_conversation_messages", ["conversation_id"], unique=False)

    op.create_table(
        "email_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("email_account_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="composed"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("recipient_emails", sa.Text, nullable=True),
        sa.Column("ai_prompt", sa.Text, nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["email_account_id"], ["email_accounts.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["email_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_drafts_workspace_id"), "email_drafts", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_email_drafts_email_account_id"), "email_drafts", ["email_account_id"], unique=False)

    op.create_table(
        "daily_email_quotas",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("email_account_id", sa.String(length=36), nullable=False),
        sa.Column("date", sa.String(length=10), nullable=False),
        sa.Column("composed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_generated_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_sent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["email_account_id"], ["email_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_daily_email_quotas_workspace_id"), "daily_email_quotas", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_daily_email_quotas_email_account_id"), "daily_email_quotas", ["email_account_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_daily_email_quotas_email_account_id"), table_name="daily_email_quotas")
    op.drop_index(op.f("ix_daily_email_quotas_workspace_id"), table_name="daily_email_quotas")
    op.drop_table("daily_email_quotas")

    op.drop_index(op.f("ix_email_drafts_email_account_id"), table_name="email_drafts")
    op.drop_index(op.f("ix_email_drafts_workspace_id"), table_name="email_drafts")
    op.drop_table("email_drafts")

    op.drop_index(op.f("ix_email_conversation_messages_conversation_id"), table_name="email_conversation_messages")
    op.drop_table("email_conversation_messages")

    op.drop_index(op.f("ix_email_conversations_lead_id"), table_name="email_conversations")
    op.drop_index(op.f("ix_email_conversations_email_account_id"), table_name="email_conversations")
    op.drop_index(op.f("ix_email_conversations_workspace_id"), table_name="email_conversations")
    op.drop_table("email_conversations")

    op.drop_index(op.f("ix_email_accounts_user_id"), table_name="email_accounts")
    op.drop_index(op.f("ix_email_accounts_workspace_id"), table_name="email_accounts")
    op.drop_table("email_accounts")
