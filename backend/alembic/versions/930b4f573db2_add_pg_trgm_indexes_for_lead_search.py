"""add pg_trgm indexes for lead search

Revision ID: 930b4f573db2
Revises: b1c2d3e4f5a6
Create Date: 2026-08-05 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "930b4f573db2"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # SQLite has no pg_trgm extension or GIN indexes; keep a lower()
        # expression index instead so the migration can run on local dev.
        op.drop_index("ix_leads_name_lower", table_name="leads")
        op.drop_index("ix_leads_company_lower", table_name="leads")
        op.drop_index("ix_leads_email_lower", table_name="leads")
        op.execute("CREATE INDEX ix_leads_name_trgm ON leads (lower(name))")
        op.execute("CREATE INDEX ix_leads_company_trgm ON leads (lower(company))")
        op.execute("CREATE INDEX ix_leads_email_trgm ON leads (lower(email))")
        return

    # The btree indexes from the previous migration can't accelerate `lower(col) LIKE '%term%'`
    # (btree needs an expression index at minimum, and even then can't serve a leading wildcard).
    # pg_trgm + GIN is what actually makes substring search fast.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.drop_index("ix_leads_name_lower", table_name="leads")
    op.drop_index("ix_leads_company_lower", table_name="leads")
    op.drop_index("ix_leads_email_lower", table_name="leads")

    op.execute("CREATE INDEX ix_leads_name_trgm ON leads USING gin (lower(name) gin_trgm_ops)")
    op.execute("CREATE INDEX ix_leads_company_trgm ON leads USING gin (lower(company) gin_trgm_ops)")
    op.execute("CREATE INDEX ix_leads_email_trgm ON leads USING gin (lower(email) gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_leads_email_trgm")
    op.execute("DROP INDEX IF EXISTS ix_leads_company_trgm")
    op.execute("DROP INDEX IF EXISTS ix_leads_name_trgm")

    op.create_index("ix_leads_name_lower", "leads", ["name"], unique=False)
    op.create_index("ix_leads_company_lower", "leads", ["company"], unique=False)
    op.create_index("ix_leads_email_lower", "leads", ["email"], unique=False)
