"""add admin role and admin_permissions rbac

Revision ID: 17ed7d600883
Revises: c4d5e6f7a8b9
Create Date: 2026-08-13 16:02:05.719600

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '17ed7d600883'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "platform_admins",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="super_admin"),
    )
    op.create_table(
        "admin_permissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("admin_id", sa.String(length=36), nullable=False),
        sa.Column("permission", sa.String(length=100), nullable=False),
        sa.Column("granted_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["platform_admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("admin_id", "permission", name="uq_admin_permission"),
    )
    op.create_index(op.f("ix_admin_permissions_admin_id"), "admin_permissions", ["admin_id"], unique=False)
    op.create_index(op.f("ix_admin_permissions_permission"), "admin_permissions", ["permission"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_permissions_permission"), table_name="admin_permissions")
    op.drop_index(op.f("ix_admin_permissions_admin_id"), table_name="admin_permissions")
    op.drop_table("admin_permissions")
    op.drop_column("platform_admins", "role")