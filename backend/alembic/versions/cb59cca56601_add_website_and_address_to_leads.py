"""add website and address to leads

Revision ID: cb59cca56601
Revises: 930b4f573db2
Create Date: 2026-08-05 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "cb59cca56601"
down_revision: Union[str, None] = "930b4f573db2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("website", sa.String(length=500), nullable=True))
    op.add_column("leads", sa.Column("address", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "address")
    op.drop_column("leads", "website")
