"""add lat/lon to leads

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-10 18:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("leads", sa.Column("lon", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "lon")
    op.drop_column("leads", "lat")
