"""add industry to leads

Revision ID: 08c8b54e1fba
Revises: d52cf7369e66
Create Date: 2026-08-06 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "08c8b54e1fba"
down_revision: Union[str, None] = "d52cf7369e66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("industry", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "industry")
