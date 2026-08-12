"""merge discovery_cache and email-thread heads

Revision ID: c4d5e6f7a8b9
Revises: a2b3c4d5e6f7, b7c8d9e0f1a2
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = ("a2b3c4d5e6f7", "b7c8d9e0f1a2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
