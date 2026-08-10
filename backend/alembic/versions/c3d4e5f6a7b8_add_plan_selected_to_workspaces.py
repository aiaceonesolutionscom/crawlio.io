"""add plan_selected to workspaces

Revision ID: c3d4e5f6a7b8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("plan_selected", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("workspaces", "plan_selected", server_default=None)


def downgrade() -> None:
    op.drop_column("workspaces", "plan_selected")
