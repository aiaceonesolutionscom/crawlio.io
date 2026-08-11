"""merge migration heads and add thread_id to email_conversations

Revision ID: a9c8b7d6e5f4
Revises: a1b2c3d4e5f6, c3d4e5f6a7b8
Create Date: 2026-08-11 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a9c8b7d6e5f4"
down_revision: Union[tuple[str, str], None] = ("a1b2c3d4e5f6", "c3d4e5f6a7b8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_conversations",
        sa.Column("thread_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_conversations", "thread_id")
