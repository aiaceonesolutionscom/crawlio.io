"""add provider_message_id and direction to email_conversation_messages

Revision ID: b7c8d9e0f1a2
Revises: a9c8b7d6e5f4
Create Date: 2026-08-11

"""
from alembic import op
import sqlalchemy as sa


revision = "b7c8d9e0f1a2"
down_revision = "a9c8b7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_conversation_messages",
        sa.Column("direction", sa.String(length=10), nullable=False, server_default="inbound"),
    )
    op.add_column(
        "email_conversation_messages",
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_email_conversation_messages_provider_message_id",
        "email_conversation_messages",
        ["provider_message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_conversation_messages_provider_message_id", table_name="email_conversation_messages")
    op.drop_column("email_conversation_messages", "provider_message_id")
    op.drop_column("email_conversation_messages", "direction")
