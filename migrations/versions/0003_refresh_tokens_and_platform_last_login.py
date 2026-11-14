"""create refresh token tables and platform admin last login

Revision ID: 0003_refresh_tokens_last_login
Revises: 0002_platform_admins
Create Date: 2026-11-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_refresh_tokens_last_login"
down_revision: str | None = "0002_platform_admins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "platform_admins",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "tenant_refresh_tokens",
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "current_generation", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("family_id", name="pk_tenant_refresh_tokens"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            ondelete="CASCADE",
            name="fk_tenant_refresh_tokens_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "tenant_id"],
            ["users.id", "users.tenant_id"],
            ondelete="CASCADE",
            name="fk_tenant_refresh_tokens_user_tenant",
        ),
    )
    op.create_index(
        "tenant_refresh_tokens_user_id_idx",
        "tenant_refresh_tokens",
        ["user_id"],
    )
    op.create_index(
        "tenant_refresh_tokens_tenant_id_idx",
        "tenant_refresh_tokens",
        ["tenant_id"],
    )

    op.create_table(
        "platform_admin_refresh_tokens",
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "current_generation", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("family_id", name="pk_platform_admin_refresh_tokens"),
        sa.ForeignKeyConstraint(
            ["platform_admin_id"],
            ["platform_admins.id"],
            ondelete="CASCADE",
            name="fk_platform_admin_refresh_tokens_admin",
        ),
    )
    op.create_index(
        "platform_admin_refresh_tokens_admin_id_idx",
        "platform_admin_refresh_tokens",
        ["platform_admin_id"],
    )

    op.execute(
        "ALTER TABLE platform_admins SET "
        "(fillfactor = 80, autovacuum_vacuum_scale_factor = 0.05, "
        "autovacuum_vacuum_threshold = 50)"
    )
    for table in ("tenant_refresh_tokens", "platform_admin_refresh_tokens"):
        op.execute(
            f"ALTER TABLE {table} SET "
            "(fillfactor = 80, autovacuum_vacuum_scale_factor = 0.05, "
            "autovacuum_vacuum_threshold = 50)"
        )


def downgrade() -> None:
    op.drop_table("platform_admin_refresh_tokens")
    op.drop_table("tenant_refresh_tokens")
    op.drop_column("platform_admins", "last_login_at")
