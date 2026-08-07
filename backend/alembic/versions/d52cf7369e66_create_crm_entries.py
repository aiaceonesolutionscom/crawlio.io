"""create crm_entries

Revision ID: d52cf7369e66
Revises: cb59cca56601
Create Date: 2026-08-06 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d52cf7369e66"
down_revision: Union[str, None] = "cb59cca56601"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crm_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "lead_id", name="uq_crm_entries_workspace_lead"),
    )
    op.create_index(op.f("ix_crm_entries_workspace_id"), "crm_entries", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_crm_entries_lead_id"), "crm_entries", ["lead_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_crm_entries_lead_id"), table_name="crm_entries")
    op.drop_index(op.f("ix_crm_entries_workspace_id"), table_name="crm_entries")
    op.drop_table("crm_entries")
