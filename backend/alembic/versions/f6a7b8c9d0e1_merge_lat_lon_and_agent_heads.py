"""merge lat/lon and business-profile/agent heads

Revision ID: f6a7b8c9d0e1
Revises: a1b2c3d4e5f6, e5f6a7b8c9d0
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = ("a1b2c3d4e5f6", "e5f6a7b8c9d0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
