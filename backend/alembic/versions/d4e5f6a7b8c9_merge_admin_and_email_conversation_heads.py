"""merge admin-panel and email-conversation-tracking heads

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8, f1a2b3c4d5e6
Create Date: 2026-08-10 18:00:00.000000

"""
from typing import Sequence, Union


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = ("c3d4e5f6a7b8", "f1a2b3c4d5e6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
