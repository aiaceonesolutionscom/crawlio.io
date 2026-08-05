"""add lead search indexes and dedup constraints

Revision ID: b1c2d3e4f5a6
Revises: a8a0114891c1
Create Date: 2026-08-05 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a8a0114891c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_leads_name_lower", "leads", ["name"], unique=False)
    op.create_index("ix_leads_company_lower", "leads", ["company"], unique=False)
    op.create_index("ix_leads_email_lower", "leads", ["email"], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_leads_workspace_email
        ON leads (workspace_id, lower(email))
        WHERE email IS NOT NULL AND email != ''
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_leads_workspace_phone
        ON leads (workspace_id, phone)
        WHERE phone IS NOT NULL AND phone != ''
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_leads_workspace_phone")
    op.execute("DROP INDEX IF EXISTS uq_leads_workspace_email")
    op.drop_index("ix_leads_email_lower", table_name="leads")
    op.drop_index("ix_leads_company_lower", table_name="leads")
    op.drop_index("ix_leads_name_lower", table_name="leads")
