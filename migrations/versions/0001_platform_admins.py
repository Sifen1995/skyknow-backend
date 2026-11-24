"""create global platform administrators tables

Revision ID: 0001_platform_admins
Revises:
Create Date: 2026-11-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_platform_admins"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0. Enable Required PostgreSQL Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")

    # 1. Create Platform Admins Table (Public Schema)
    op.create_table(
        "platform_admins",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("mfa_secret", sa.String(length=255), nullable=True),
        sa.Column(
            "is_super_superuser",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_platform_admins"),
        sa.UniqueConstraint("email", name="uq_platform_admins_email"),
    )

    # 2. Create Platform Admin Refresh Tokens (Public Schema)
    op.create_table(
        "platform_admin_refresh_tokens",
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "current_generation",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
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

    # 3. Performance Tuning (Vacuum settings for Global Tables only)
    for table in ("platform_admins", "platform_admin_refresh_tokens"):
        op.execute(
            f"ALTER TABLE {table} SET "
            "(fillfactor = 80, autovacuum_vacuum_scale_factor = 0.05, "
            "autovacuum_vacuum_threshold = 50)"
        )


def downgrade() -> None:
    op.drop_table("platform_admin_refresh_tokens")
    op.drop_table("platform_admins")


# """initial auth and multi_tenant org schema with FK indexes and HOT optimization

# Revision ID: 0001_initial_auth_org
# Revises:
# Create Date: 2026-11-09 11:05:00.000000

# """

# from collections.abc import Sequence
# from typing import Any

# import sqlalchemy as sa
# from alembic import op
# from sqlalchemy.dialects import postgresql
# from sqlalchemy.types import UserDefinedType

# # revision identifiers, used by Alembic.
# revision: str = "0001_initial_auth_org"
# down_revision: str | None = None
# branch_labels: str | Sequence[str] | None = None
# depends_on: str | Sequence[str] | None = None


# class LtreeType(UserDefinedType[Any]):
#     cache_ok = True

#     def get_col_spec(self, **kwargs: object) -> str:
#         return "LTREE"


# def upgrade() -> None:
#     # 1. Enable Required PostgreSQL Extensions
#     op.execute("CREATE EXTENSION IF NOT EXISTS ltree;")
#     op.execute("CREATE EXTENSION IF NOT EXISTS citext;")

#     # 2. Define PostgreSQL Enum Types
#     hosting_mode_enum = postgresql.ENUM(
#         "shared", "dedicated", name="hosting_mode_enum", create_type=False
#     )
#     tenant_status_enum = postgresql.ENUM(
#         "provisioning",
#         "active",
#         "suspended",
#         name="tenant_status_enum",
#         create_type=False,
#     )
#     idp_type_enum = postgresql.ENUM(
#         "oidc", "saml", "ldap", "standalone", name="idp_type_enum", create_type=False
#     )
#     user_status_enum = postgresql.ENUM(
#         "pending", "active", "disabled", name="user_status_enum", create_type=False
#     )
#     system_role_enum = postgresql.ENUM(
#         "author",
#         "reviewer",
#         "publisher",
#         "admin",
#         name="system_role_enum",
#         create_type=False,
#     )
#     role_scope_enum = postgresql.ENUM(
#         "own_unit",
#         "unit_and_below",
#         "company",
#         name="role_scope_enum",
#         create_type=False,
#     )

#     for enum_type in [
#         hosting_mode_enum,
#         tenant_status_enum,
#         idp_type_enum,
#         user_status_enum,
#         system_role_enum,
#         role_scope_enum,
#     ]:
#         enum_type.create(op.get_bind(), checkfirst=True)

#     # 3. TENANTS (Platform-Level Table - Exempt from RLS)
#     op.create_table(
#         "tenants",
#         sa.Column(
#             "id",
#             postgresql.UUID(as_uuid=True),
#             server_default=sa.text("gen_random_uuid()"),
#             nullable=False,
#         ),
#         sa.Column("name", sa.String(length=150), nullable=False),
#         sa.Column("subdomain", postgresql.CITEXT(), nullable=False),
#         sa.Column("custom_domain", postgresql.CITEXT(), nullable=True),
#         sa.Column(
#             "hosting_mode", hosting_mode_enum, server_default="shared", nullable=False
#         ),
#         sa.Column(
#             "status", tenant_status_enum, server_default="provisioning", nullable=False
#         ),
#         sa.Column(
#             "created_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.Column(
#             "updated_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.PrimaryKeyConstraint("id", name="pk_tenants"),
#         sa.UniqueConstraint("subdomain", name="uq_tenants_subdomain"),
#         sa.UniqueConstraint("custom_domain", name="uq_tenants_custom_domain"),
#         sa.CheckConstraint(
#             "subdomain ~ '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$'",
#             name="ck_tenants_subdomain_format",
#         ),
#     )

#     # 4. UNIT TYPES (Admin-defined node classifications, e.g., Division, Call_Center)
#     op.create_table(
#         "unit_types",
#         sa.Column(
#             "id",
#             postgresql.UUID(as_uuid=True),
#             server_default=sa.text("gen_random_uuid()"),
#             nullable=False,
#         ),
#         sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column("name", sa.String(length=100), nullable=False),
#         sa.Column("level", sa.SmallInteger(), nullable=False),
#         sa.Column(
#             "capabilities",
#             postgresql.JSONB(astext_type=sa.Text()),
#             server_default=sa.text("'{}'::jsonb"),
#             nullable=False,
#         ),
#         sa.Column(
#             "created_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.PrimaryKeyConstraint("id", name="pk_unit_types"),
#         sa.ForeignKeyConstraint(
#             ["tenant_id"],
#             ["tenants.id"],
#             name="fk_unit_types_tenant",
#             ondelete="CASCADE",
#         ),
#         sa.UniqueConstraint("tenant_id", "name", name="uq_unit_types_tenant_name"),
#         sa.UniqueConstraint("id", "tenant_id", name="uq_unit_types_id_tenant"),
#         sa.CheckConstraint("level >= 0", name="ck_unit_types_positive_level"),
#     )
#     op.create_index("ix_unit_types_tenant_id", "unit_types", ["tenant_id"])

#     # 5. ORGANISATION UNITS (Hierarchical tree using PostgreSQL ltree)
#     op.create_table(
#         "organisation_units",
#         sa.Column(
#             "id",
#             postgresql.UUID(as_uuid=True),
#             server_default=sa.text("gen_random_uuid()"),
#             nullable=False,
#         ),
#         sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column("unit_type_id", postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
#         sa.Column("name", sa.String(length=150), nullable=False),
#         sa.Column("slug", sa.String(length=64), nullable=False),
#         sa.Column("path", LtreeType(), nullable=False),
#         sa.Column(
#             "created_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.Column(
#             "updated_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.PrimaryKeyConstraint("id", name="pk_organisation_units"),
#         sa.ForeignKeyConstraint(
#             ["tenant_id"],
#             ["tenants.id"],
#             name="fk_org_units_tenant",
#             ondelete="CASCADE",
#         ),
#         sa.ForeignKeyConstraint(
#             ["unit_type_id", "tenant_id"],
#             ["unit_types.id", "unit_types.tenant_id"],
#             name="fk_org_units_unit_type_tenant",
#             ondelete="RESTRICT",
#         ),
#         sa.ForeignKeyConstraint(
#             ["parent_id", "tenant_id"],
#             ["organisation_units.id", "organisation_units.tenant_id"],
#             name="fk_org_units_parent_tenant",
#             ondelete="RESTRICT",
#         ),
#         sa.UniqueConstraint("id", "tenant_id", name="uq_org_units_id_tenant"),
#         sa.UniqueConstraint("tenant_id", "path", name="uq_org_units_tenant_path"),
#         sa.CheckConstraint("id != parent_id", name="ck_org_units_no_self_parent"),
#         sa.CheckConstraint(
#             "slug ~ '^[a-z0-9_]+$'", name="ck_org_units_valid_ltree_slug"
#         ),
#     )
#     op.create_index(
#         "ix_org_units_path_gist",
#         "organisation_units",
#         ["path"],
#         postgresql_using="gist",
#     )
#     op.create_index("ix_org_units_tenant_id", "organisation_units", ["tenant_id"])
#     # FK indexes for organisation_units
#     op.create_index("ix_org_units_unit_type_id", "organisation_units", ["unit_type_id"])
#     op.create_index("ix_org_units_parent_id", "organisation_units", ["parent_id"])

#     # 6. IDENTITY PROVIDERS (Per-company OIDC, SAML, LDAP, or Standalone config)
#     op.create_table(
#         "identity_providers",
#         sa.Column(
#             "id",
#             postgresql.UUID(as_uuid=True),
#             server_default=sa.text("gen_random_uuid()"),
#             nullable=False,
#         ),
#         sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column("name", sa.String(length=100), nullable=False),
#         sa.Column("type", idp_type_enum, nullable=False),
#         sa.Column(
#             "settings",
#             postgresql.JSONB(astext_type=sa.Text()),
#             server_default=sa.text("'{}'::jsonb"),
#             nullable=False,
#         ),
#         sa.Column(
#             "auto_login_enabled",
#             sa.Boolean(),
#             server_default=sa.text("false"),
#             nullable=False,
#         ),
#         sa.Column(
#             "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
#         ),
#         sa.Column(
#             "created_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.PrimaryKeyConstraint("id", name="pk_identity_providers"),
#         sa.ForeignKeyConstraint(
#             ["tenant_id"], ["tenants.id"], name="fk_idp_tenant", ondelete="CASCADE"
#         ),
#         sa.UniqueConstraint("id", "tenant_id", name="uq_idp_id_tenant"),
#         sa.UniqueConstraint("tenant_id", "name", name="uq_idp_tenant_name"),
#         sa.CheckConstraint(
#             "NOT (type = 'standalone' AND auto_login_enabled = true)",
#             name="ck_idp_no_standalone_autologin",
#         ),
#     )
#     op.create_index(
#         "ix_identity_providers_tenant_id", "identity_providers", ["tenant_id"]
#     )
#     op.create_index(
#         "ix_idp_one_autologin_per_tenant",
#         "identity_providers",
#         ["tenant_id"],
#         unique=True,
#         postgresql_where=sa.text("auto_login_enabled = true AND is_active = true"),
#     )

#     # 7. ROLES TABLE
#     op.create_table(
#         "roles",
#         sa.Column(
#             "id",
#             postgresql.UUID(as_uuid=True),
#             server_default=sa.text("gen_random_uuid()"),
#             nullable=False,
#         ),
#         sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column("name", system_role_enum, nullable=False),
#         sa.Column(
#             "scope", role_scope_enum, server_default="unit_and_below", nullable=False
#         ),
#         sa.Column("description", sa.String(length=255), nullable=True),
#         sa.Column(
#             "created_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.PrimaryKeyConstraint("id", name="pk_roles"),
#         sa.ForeignKeyConstraint(
#             ["tenant_id"], ["tenants.id"], name="fk_roles_tenant", ondelete="CASCADE"
#         ),
#         sa.UniqueConstraint("id", "tenant_id", name="uq_roles_id_tenant"),
#         sa.UniqueConstraint(
#             "tenant_id", "name", "scope", name="uq_roles_tenant_name_scope"
#         ),
#     )
#     op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])

#     # 8. USERS (Reserve page space for HOT updates to frequently changed columns)
#     op.create_table(
#         "users",
#         sa.Column(
#             "id",
#             postgresql.UUID(as_uuid=True),
#             server_default=sa.text("gen_random_uuid()"),
#             nullable=False,
#         ),
#         sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column(
#             "organisation_unit_id", postgresql.UUID(as_uuid=True), nullable=False
#         ),
#         sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
#         sa.Column("name", sa.String(length=150), nullable=False),
#         sa.Column("email", postgresql.CITEXT(), nullable=False),
#         sa.Column("status", user_status_enum, server_default="active", nullable=False),
#         sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
#         sa.Column(
#             "created_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.Column(
#             "updated_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.PrimaryKeyConstraint("id", name="pk_users"),
#         sa.ForeignKeyConstraint(
#             ["tenant_id"], ["tenants.id"], name="fk_users_tenant", ondelete="CASCADE"
#         ),
#         sa.ForeignKeyConstraint(
#             ["organisation_unit_id", "tenant_id"],
#             ["organisation_units.id", "organisation_units.tenant_id"],
#             name="fk_users_org_unit_tenant",
#             ondelete="RESTRICT",
#         ),
#         sa.ForeignKeyConstraint(
#             ["role_id", "tenant_id"],
#             ["roles.id", "roles.tenant_id"],
#             name="fk_users_role_tenant",
#             ondelete="SET NULL",
#         ),
#         sa.UniqueConstraint("id", "tenant_id", name="uq_users_id_tenant"),
#         sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
#     )
#     op.execute("ALTER TABLE users SET (fillfactor = 80);")
#     op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
#     op.create_index(
#         "ix_users_tenant_org_unit", "users", ["tenant_id", "organisation_unit_id"]
#     )
#     # Explicit FK indexes for users table
#     op.create_index("ix_users_organisation_unit_id", "users", ["organisation_unit_id"])
#     op.create_index("ix_users_role_id", "users", ["role_id"])

#     # Apply aggressive autovacuum tuning on users table to keep dead tuples cleaned up
#     op.execute(
#         "ALTER TABLE users SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_vacuum_threshold = 50);"
#     )

#     # 9. USER IDENTITIES
#     op.create_table(
#         "user_identities",
#         sa.Column(
#             "id",
#             postgresql.UUID(as_uuid=True),
#             server_default=sa.text("gen_random_uuid()"),
#             nullable=False,
#         ),
#         sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column(
#             "identity_provider_id", postgresql.UUID(as_uuid=True), nullable=False
#         ),
#         sa.Column("provider_user_id", sa.String(length=255), nullable=False),
#         sa.Column("password_hash", sa.String(length=255), nullable=True),
#         sa.Column("mfa_secret", sa.String(length=255), nullable=True),
#         sa.Column(
#             "mfa_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
#         ),
#         sa.Column(
#             "created_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.PrimaryKeyConstraint("id", name="pk_user_identities"),
#         sa.ForeignKeyConstraint(
#             ["user_id", "tenant_id"],
#             ["users.id", "users.tenant_id"],
#             name="fk_user_identities_user_tenant",
#             ondelete="CASCADE",
#         ),
#         sa.ForeignKeyConstraint(
#             ["identity_provider_id", "tenant_id"],
#             ["identity_providers.id", "identity_providers.tenant_id"],
#             name="fk_user_identities_idp_tenant",
#             ondelete="RESTRICT",
#         ),
#         sa.UniqueConstraint(
#             "identity_provider_id",
#             "provider_user_id",
#             name="uq_user_identities_idp_subject",
#         ),
#         sa.UniqueConstraint(
#             "user_id", "identity_provider_id", name="uq_user_identities_user_idp"
#         ),
#     )
#     op.create_index("ix_user_identities_tenant_id", "user_identities", ["tenant_id"])
#     # Explicit FK indexes for user_identities table
#     op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])
#     op.create_index(
#         "ix_user_identities_identity_provider_id",
#         "user_identities",
#         ["identity_provider_id"],
#     )

#     # 10. GROUP MAPPINGS
#     op.create_table(
#         "group_mappings",
#         sa.Column(
#             "id",
#             postgresql.UUID(as_uuid=True),
#             server_default=sa.text("gen_random_uuid()"),
#             nullable=False,
#         ),
#         sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column(
#             "identity_provider_id", postgresql.UUID(as_uuid=True), nullable=False
#         ),
#         sa.Column("external_group_key", sa.String(length=255), nullable=False),
#         sa.Column(
#             "organisation_unit_id", postgresql.UUID(as_uuid=True), nullable=False
#         ),
#         sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
#         sa.Column("priority", sa.SmallInteger(), server_default="100", nullable=False),
#         sa.Column(
#             "created_at",
#             sa.DateTime(timezone=True),
#             server_default=sa.text("now()"),
#             nullable=False,
#         ),
#         sa.PrimaryKeyConstraint("id", name="pk_group_mappings"),
#         sa.ForeignKeyConstraint(
#             ["identity_provider_id", "tenant_id"],
#             ["identity_providers.id", "identity_providers.tenant_id"],
#             name="fk_group_mappings_idp_tenant",
#             ondelete="CASCADE",
#         ),
#         sa.ForeignKeyConstraint(
#             ["organisation_unit_id", "tenant_id"],
#             ["organisation_units.id", "organisation_units.tenant_id"],
#             name="fk_group_mappings_org_unit_tenant",
#             ondelete="CASCADE",
#         ),
#         sa.ForeignKeyConstraint(
#             ["role_id", "tenant_id"],
#             ["roles.id", "roles.tenant_id"],
#             name="fk_group_mappings_role_tenant",
#             ondelete="SET NULL",
#         ),
#         sa.UniqueConstraint(
#             "identity_provider_id",
#             "external_group_key",
#             name="uq_group_mapping_idp_external_group",
#         ),
#     )
#     op.create_index("ix_group_mappings_tenant_id", "group_mappings", ["tenant_id"])
#     # Explicit FK indexes for group_mappings table
#     op.create_index(
#         "ix_group_mappings_identity_provider_id",
#         "group_mappings",
#         ["identity_provider_id"],
#     )
#     op.create_index(
#         "ix_group_mappings_organisation_unit_id",
#         "group_mappings",
#         ["organisation_unit_id"],
#     )
#     op.create_index("ix_group_mappings_role_id", "group_mappings", ["role_id"])

#     # 11. Enable PostgreSQL Row-Level Security (RLS) on all Tenant-Scoped Tables
#     tenant_scoped_tables = [
#         "unit_types",
#         "organisation_units",
#         "identity_providers",
#         "roles",
#         "users",
#         "user_identities",
#         "group_mappings",
#     ]
#     for table in tenant_scoped_tables:
#         op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
#         op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
#         op.execute(
#             f"""
#             CREATE POLICY {table}_tenant_isolation_policy ON {table}
#             USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
#             WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
#             """
#         )


# def downgrade() -> None:
#     tenant_scoped_tables = [
#         "group_mappings",
#         "user_identities",
#         "users",
#         "roles",
#         "identity_providers",
#         "organisation_units",
#         "unit_types",
#     ]
#     for table in tenant_scoped_tables:
#         op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_policy ON {table};")
#         op.drop_table(table)

#     op.drop_table("tenants")

#     for enum_name in [
#         "role_scope_enum",
#         "system_role_enum",
#         "user_status_enum",
#         "idp_type_enum",
#         "tenant_status_enum",
#         "hosting_mode_enum",
#     ]:
#         postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
