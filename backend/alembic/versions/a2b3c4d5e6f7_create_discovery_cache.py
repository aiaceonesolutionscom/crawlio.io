"""create discovery_cache

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "discovery_cache",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("niche_key", sa.String(length=120), nullable=False),
        sa.Column("city_key", sa.String(length=120), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("niche", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=120), nullable=False),
        sa.Column("items", sa.JSON, nullable=False),
        sa.Column("item_count", sa.Integer, nullable=False),
        sa.Column("source_counts", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("niche_key", "city_key", "country_code", name="uq_discovery_cache_key"),
    )
    op.create_index(op.f("ix_discovery_cache_niche_key"), "discovery_cache", ["niche_key"], unique=False)
    op.create_index(op.f("ix_discovery_cache_city_key"), "discovery_cache", ["city_key"], unique=False)
    op.create_index(op.f("ix_discovery_cache_country_code"), "discovery_cache", ["country_code"], unique=False)
    op.create_index(op.f("ix_discovery_cache_expires_at"), "discovery_cache", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_discovery_cache_expires_at"), table_name="discovery_cache")
    op.drop_index(op.f("ix_discovery_cache_country_code"), table_name="discovery_cache")
    op.drop_index(op.f("ix_discovery_cache_city_key"), table_name="discovery_cache")
    op.drop_index(op.f("ix_discovery_cache_niche_key"), table_name="discovery_cache")
    op.drop_table("discovery_cache")
