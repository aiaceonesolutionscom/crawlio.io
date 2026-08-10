"""add customer tracking columns to email_conversations

Revision ID: f1a2b3c4d5e6
Revises: e1f2g3h4i5j6
Create Date: 2026-08-07 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e1f2g3h4i5j6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_conversations",
        sa.Column("customer_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "email_conversations",
        sa.Column("customer_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "email_conversations",
        sa.Column("last_processed_message_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        op.f("ix_email_conversations_customer_email"),
        "email_conversations",
        ["customer_email"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_conversations_customer_email"), table_name="email_conversations")
    op.drop_column("email_conversations", "last_processed_message_id")
    op.drop_column("email_conversations", "customer_name")
    op.drop_column("email_conversations", "customer_email")