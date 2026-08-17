"""create platform_admins plan_configs feature_flags feature_flag_overrides system_settings audit_log, seed plan_configs

Revision ID: f2a3b4c5d6e7
Revises: e1f2g3h4i5j6
Create Date: 2026-08-07 16:30:00.000000

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2g3h4i5j6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same values as app/core/plans.py at the time of this migration, so the
# cutover to DB-driven plan config is behavior-identical to what shipped before.
_PLAN_SEED = [
    {
        "plan_key": "free",
        "display_name": "Free",
        "lead_quota": 500,
        "seat_quota": 1,
        "discovery_result_limit": 50,
        "daily_discovery_import_limit": 50,
        "daily_email_limit": 0,
        "capabilities": ["leads", "workspaces", "lead_discovery", "export"],
        "sort_order": 0,
    },
    {
        "plan_key": "pro",
        "display_name": "Pro",
        "lead_quota": 5000,
        "seat_quota": 10,
        "discovery_result_limit": 100,
        "daily_discovery_import_limit": 100,
        "daily_email_limit": 100,
        "capabilities": [
            "leads", "workspaces", "automation", "analytics", "team", "whatsapp", "export",
            "lead_discovery", "lead_discovery_enhanced", "ai_lead_filter", "email_agent",
        ],
        "sort_order": 1,
    },
    {
        "plan_key": "enterprise",
        "display_name": "Enterprise",
        "lead_quota": 1_000_000_000,
        "seat_quota": 1_000_000_000,
        "discovery_result_limit": 200,
        "daily_discovery_import_limit": 200,
        "daily_email_limit": 500,
        "capabilities": [
            "leads", "workspaces", "automation", "analytics", "team", "whatsapp", "branding", "sso", "export",
            "lead_discovery", "lead_discovery_enhanced", "ai_lead_filter", "email_agent",
        ],
        "sort_order": 2,
    },
]


def upgrade() -> None:
    op.create_table(
        "platform_admins",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("clerk_user_id", sa.String(length=255), nullable=True),
        sa.Column("added_by", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_platform_admins_email"), "platform_admins", ["email"], unique=True)
    op.create_index(op.f("ix_platform_admins_clerk_user_id"), "platform_admins", ["clerk_user_id"], unique=True)

    op.create_table(
        "plan_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_key", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("lead_quota", sa.Integer, nullable=False, server_default="0"),
        sa.Column("seat_quota", sa.Integer, nullable=False, server_default="0"),
        sa.Column("discovery_result_limit", sa.Integer, nullable=False, server_default="0"),
        sa.Column("daily_discovery_import_limit", sa.Integer, nullable=False, server_default="0"),
        sa.Column("daily_email_limit", sa.Integer, nullable=False, server_default="0"),
        sa.Column("capabilities", sa.JSON, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plan_configs_plan_key"), "plan_configs", ["plan_key"], unique=True)

    op.create_table(
        "feature_flags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("default_enabled", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feature_flags_key"), "feature_flags", ["key"], unique=True)

    op.create_table(
        "feature_flag_overrides",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("flag_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["flag_id"], ["feature_flags.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flag_id", "workspace_id", name="uq_feature_flag_override_flag_workspace"),
    )

    op.create_table(
        "system_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON, nullable=True),
        sa.Column("value_type", sa.String(length=20), nullable=False, server_default="string"),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_system_settings_key"), "system_settings", ["key"], unique=True)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_email", sa.String(length=255), nullable=False),
        sa.Column("actor_clerk_user_id", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("before", sa.JSON, nullable=True),
        sa.Column("after", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_actor_email"), "audit_log", ["actor_email"], unique=False)
    op.create_index(op.f("ix_audit_log_actor_clerk_user_id"), "audit_log", ["actor_clerk_user_id"], unique=False)
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_audit_log_target_type"), "audit_log", ["target_type"], unique=False)
    op.create_index(op.f("ix_audit_log_target_id"), "audit_log", ["target_id"], unique=False)
    op.create_index(op.f("ix_audit_log_workspace_id"), "audit_log", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False)

    plan_configs_table = sa.table(
        "plan_configs",
        sa.column("id", sa.String),
        sa.column("plan_key", sa.String),
        sa.column("display_name", sa.String),
        sa.column("lead_quota", sa.Integer),
        sa.column("seat_quota", sa.Integer),
        sa.column("discovery_result_limit", sa.Integer),
        sa.column("daily_discovery_import_limit", sa.Integer),
        sa.column("daily_email_limit", sa.Integer),
        sa.column("capabilities", sa.JSON),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    seeded_at = datetime.now(timezone.utc)
    op.bulk_insert(
        plan_configs_table,
        [
            {
                "id": str(uuid.uuid4()),
                "plan_key": p["plan_key"],
                "display_name": p["display_name"],
                "lead_quota": p["lead_quota"],
                "seat_quota": p["seat_quota"],
                "discovery_result_limit": p["discovery_result_limit"],
                "daily_discovery_import_limit": p["daily_discovery_import_limit"],
                "daily_email_limit": p["daily_email_limit"],
                "capabilities": p["capabilities"],
                "sort_order": p["sort_order"],
                "is_active": True,
                "created_at": seeded_at,
                "updated_at": seeded_at,
            }
            for p in _PLAN_SEED
        ],
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_system_settings_key"), table_name="system_settings")
    op.drop_table("system_settings")
    op.drop_table("feature_flag_overrides")
    op.drop_index(op.f("ix_feature_flags_key"), table_name="feature_flags")
    op.drop_table("feature_flags")
    op.drop_index(op.f("ix_plan_configs_plan_key"), table_name="plan_configs")
    op.drop_table("plan_configs")
    op.drop_index(op.f("ix_platform_admins_clerk_user_id"), table_name="platform_admins")
    op.drop_index(op.f("ix_platform_admins_email"), table_name="platform_admins")
    op.drop_table("platform_admins")
