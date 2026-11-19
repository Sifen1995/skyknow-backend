import argparse
import asyncio
import os
import re
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Ensure project root is in sys.path when running script directly
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from app.config import settings
from app.core.security import hash_password

DATABASE_URL = os.getenv("DATABASE_URL", str(settings.DATABASE_URL))
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


def generate_schema_name(subdomain: str) -> str:
    clean = re.sub(r"[^a-z0-9]", "_", subdomain.lower()).strip("_")
    return f"tenant_{clean}"


def get_tenant_ddl() -> str:
    """
    The exact DDL for tenant tables, adapted for Schema-per-Tenant.
    Notice that tenant_id, RLS policies, and RLS composite indexes are removed.
    Indexes are added for foreign keys and frequent lookups, while frequently
    updated columns (last_login_at, updated_at) are intentionally unindexed
    to allow PostgreSQL Heap-Only Tuple (HOT) updates.
    """
    return """
    -- 1. Extensions & Enums
    CREATE EXTENSION IF NOT EXISTS ltree WITH SCHEMA public;
    CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;

    DO $$ BEGIN
        CREATE TYPE idp_type_enum AS ENUM ('oidc', 'saml', 'ldap', 'standalone');
        CREATE TYPE user_status_enum AS ENUM ('pending', 'active', 'disabled');
        CREATE TYPE system_role_enum AS ENUM ('author', 'reviewer', 'publisher', 'admin');
        CREATE TYPE role_scope_enum AS ENUM ('own_unit', 'unit_and_below', 'company');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;

    -- 2. UNIT TYPES
    CREATE TABLE IF NOT EXISTS unit_types (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(100) NOT NULL UNIQUE,
        level SMALLINT NOT NULL CHECK (level >= 0),
        capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- 3. ORGANISATION UNITS
    CREATE TABLE IF NOT EXISTS organisation_units (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        unit_type_id UUID NOT NULL REFERENCES unit_types(id) ON DELETE RESTRICT,
        parent_id UUID REFERENCES organisation_units(id) ON DELETE RESTRICT,
        name VARCHAR(150) NOT NULL,
        slug VARCHAR(64) NOT NULL CHECK (slug ~ '^[a-z0-9_]+$'),
        path LTREE NOT NULL UNIQUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK (id != parent_id)
    );
    CREATE INDEX IF NOT EXISTS ix_org_units_path_gist ON organisation_units USING gist (path);
    CREATE INDEX IF NOT EXISTS ix_org_units_unit_type_id ON organisation_units (unit_type_id);
    CREATE INDEX IF NOT EXISTS ix_org_units_parent_id ON organisation_units (parent_id);

    -- 4. IDENTITY PROVIDERS
    CREATE TABLE IF NOT EXISTS identity_providers (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(100) NOT NULL UNIQUE,
        type idp_type_enum NOT NULL,
        settings JSONB NOT NULL DEFAULT '{}'::jsonb,
        auto_login_enabled BOOLEAN NOT NULL DEFAULT false,
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK (NOT (type = 'standalone' AND auto_login_enabled = true))
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ix_idp_one_autologin ON identity_providers (auto_login_enabled) 
    WHERE auto_login_enabled = true AND is_active = true;
    CREATE INDEX IF NOT EXISTS ix_identity_providers_type ON identity_providers (type);

    -- 5. ROLES
    CREATE TABLE IF NOT EXISTS roles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name system_role_enum NOT NULL,
        scope role_scope_enum NOT NULL DEFAULT 'unit_and_below',
        description VARCHAR(255),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (name, scope)
    );

    -- 6. USERS
    -- fillfactor = 80 reserves 20% page headroom for in-place Heap-Only Tuple (HOT) updates.
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organisation_unit_id UUID NOT NULL REFERENCES organisation_units(id) ON DELETE RESTRICT,
        role_id UUID REFERENCES roles(id) ON DELETE SET NULL,
        name VARCHAR(150) NOT NULL,
        email CITEXT NOT NULL UNIQUE,
        status user_status_enum NOT NULL DEFAULT 'active',
        last_login_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    ) WITH (fillfactor = 80, autovacuum_vacuum_scale_factor = 0.05, autovacuum_vacuum_threshold = 50);

    -- Indexes on foreign keys and filtering columns:
    CREATE INDEX IF NOT EXISTS ix_users_org_unit_id ON users (organisation_unit_id);
    CREATE INDEX IF NOT EXISTS ix_users_role_id ON users (role_id);
    CREATE INDEX IF NOT EXISTS ix_users_status ON users (status);

    -- =========================================================================
    -- CRITICAL HOT UPDATE (HEAP-ONLY TUPLES) OPTIMIZATION:
    -- Frequently updated columns ('last_login_at' and 'updated_at') are
    -- intentionally NOT indexed. In PostgreSQL, an UPDATE cannot be a HOT update
    -- if any indexed column changes. By leaving 'last_login_at' and 'updated_at'
    -- unindexed and setting fillfactor = 80, login timestamps and touch updates
    -- remain within the same heap page, avoiding index write amplification and bloat.
    -- =========================================================================

    -- 7. USER IDENTITIES
    CREATE TABLE IF NOT EXISTS user_identities (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        identity_provider_id UUID NOT NULL REFERENCES identity_providers(id) ON DELETE RESTRICT,
        provider_user_id VARCHAR(255) NOT NULL,
        password_hash VARCHAR(255),
        mfa_secret VARCHAR(255),
        mfa_enabled BOOLEAN NOT NULL DEFAULT false,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (identity_provider_id, provider_user_id),
        UNIQUE (user_id, identity_provider_id)
    );
    CREATE INDEX IF NOT EXISTS ix_user_identities_user_id ON user_identities (user_id);
    CREATE INDEX IF NOT EXISTS ix_user_identities_identity_provider_id ON user_identities (identity_provider_id);

    -- 8. GROUP MAPPINGS
    CREATE TABLE IF NOT EXISTS group_mappings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        identity_provider_id UUID NOT NULL REFERENCES identity_providers(id) ON DELETE CASCADE,
        external_group_key VARCHAR(255) NOT NULL,
        organisation_unit_id UUID NOT NULL REFERENCES organisation_units(id) ON DELETE CASCADE,
        role_id UUID REFERENCES roles(id) ON DELETE SET NULL,
        priority SMALLINT NOT NULL DEFAULT 100,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (identity_provider_id, external_group_key)
    );
    CREATE INDEX IF NOT EXISTS ix_group_mappings_org_unit_id ON group_mappings (organisation_unit_id);
    CREATE INDEX IF NOT EXISTS ix_group_mappings_role_id ON group_mappings (role_id);

    -- 9. REFRESH TOKENS (Mirrors platform_admin_refresh_tokens column structure)
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        family_id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        current_generation INTEGER NOT NULL DEFAULT 1,
        secret_hash VARCHAR(64) NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        revoked_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    ) WITH (fillfactor = 80, autovacuum_vacuum_scale_factor = 0.05, autovacuum_vacuum_threshold = 50);
    CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id);

    -- Alias view so queries referencing user_refresh_tokens also work
    CREATE OR REPLACE VIEW user_refresh_tokens AS SELECT * FROM refresh_tokens;

    -- 10. TENANT SCHEMA VERSION TRACKER
    -- Tracks applied schema migration scripts per tenant to ensure idempotent schema upgrades.
    CREATE TABLE IF NOT EXISTS schema_versions (
        version VARCHAR(100) PRIMARY KEY,
        description VARCHAR(255),
        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    INSERT INTO schema_versions (version, description)
    VALUES ('0001_initial_schema', 'Initial tenant schema tables, indexes, and constraints')
    ON CONFLICT (version) DO NOTHING;
    """


async def provision_tenant_and_admin(
    *,
    subdomain: str,
    admin_email: str,
    admin_name: str,
    temporary_password: str | None = None,
    hosting_mode: str = "shared",
    custom_domain: str | None = None,
    primary_color: str | None = None,
    logo_url: str | None = None,
    name: str | None = None,
) -> None:
    schema_name = generate_schema_name(subdomain)
    tenant_name = name or subdomain.replace("_", " ").replace("-", " ").title()
    tenant_id = str(uuid.uuid4())

    async with async_session_maker() as session:
        try:
            # 1. Register Tenant in the GLOBAL public schema (ensure table and custom_domain exist)
            await session.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS public.tenants (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name VARCHAR(150) NOT NULL,
                        subdomain VARCHAR(64) NOT NULL UNIQUE,
                        custom_domain VARCHAR(255) UNIQUE,
                        hosting_mode VARCHAR(32) NOT NULL DEFAULT 'shared',
                        primary_color VARCHAR(32),
                        logo_url VARCHAR(500),
                        status VARCHAR(32) NOT NULL DEFAULT 'active',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS custom_domain VARCHAR(255) UNIQUE;
                    ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS primary_color VARCHAR(32);
                    ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS logo_url VARCHAR(500);
                """)
            )
            await session.execute(
                text("""
                    INSERT INTO public.tenants (id, name, subdomain, custom_domain, hosting_mode, primary_color, logo_url, status)
                    VALUES (:id, :name, :subdomain, :custom_domain, :hosting_mode, :primary_color, :logo_url, 'active')
                    ON CONFLICT (subdomain) DO UPDATE SET
                        name = EXCLUDED.name,
                        custom_domain = EXCLUDED.custom_domain,
                        hosting_mode = EXCLUDED.hosting_mode,
                        primary_color = EXCLUDED.primary_color,
                        logo_url = EXCLUDED.logo_url,
                        status = 'active',
                        updated_at = now()
                """),
                {
                    "id": tenant_id,
                    "name": tenant_name,
                    "subdomain": subdomain,
                    "custom_domain": custom_domain,
                    "hosting_mode": hosting_mode,
                    "primary_color": primary_color,
                    "logo_url": logo_url,
                },
            )

            # 2. Create the Schema
            await session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

            # 3. Execute the multi-statement DDL via the raw driver connection (Simple Query protocol)
            conn = await session.connection()
            raw_conn = await conn.get_raw_connection()
            ddl_script = (
                f'SET search_path TO "{schema_name}", public;\n' + get_tenant_ddl()
            )
            await raw_conn.driver_connection.execute(ddl_script)

            # Keep search path set for following session queries
            await session.execute(text(f'SET search_path TO "{schema_name}", public'))

            # 4. Seed Default Organization Structure: Role, Unit Type, Org Unit
            # -> Create 'admin' role
            role_id = str(uuid.uuid4())
            await session.execute(
                text("""
                    INSERT INTO roles (id, name, scope, description) 
                    VALUES (:id, 'admin', 'company', 'Full Platform Administrator')
                    ON CONFLICT (name, scope) DO NOTHING
                """),
                {"id": role_id},
            )
            role_result = await session.execute(
                text("SELECT id FROM roles WHERE name = 'admin' AND scope = 'company'")
            )
            role_id = str(role_result.scalar_one())

            # -> Create 'Headquarters' unit type
            unit_type_id = str(uuid.uuid4())
            await session.execute(
                text("""
                    INSERT INTO unit_types (id, name, level) 
                    VALUES (:id, 'Headquarters', 0)
                    ON CONFLICT (name) DO NOTHING
                """),
                {"id": unit_type_id},
            )
            unit_type_result = await session.execute(
                text("SELECT id FROM unit_types WHERE name = 'Headquarters'")
            )
            unit_type_id = str(unit_type_result.scalar_one())

            # -> Create Root Organisation Unit
            org_unit_id = str(uuid.uuid4())
            await session.execute(
                text("""
                    INSERT INTO organisation_units (id, unit_type_id, name, slug, path) 
                    VALUES (:id, :ut_id, 'Headquarters', 'hq', 'hq')
                    ON CONFLICT (path) DO NOTHING
                """),
                {"id": org_unit_id, "ut_id": unit_type_id},
            )
            org_unit_result = await session.execute(
                text("SELECT id FROM organisation_units WHERE path = 'hq'")
            )
            org_unit_id = str(org_unit_result.scalar_one())

            # 5. Create Tenant Admin directly in the users table (distinguished by role_id)
            admin_user_id = str(uuid.uuid4())
            await session.execute(
                text("""
                    INSERT INTO users (id, organisation_unit_id, role_id, name, email, status) 
                    VALUES (:id, :org_unit_id, :role_id, :name, :email, 'active')
                    ON CONFLICT (email) DO UPDATE SET
                        role_id = EXCLUDED.role_id,
                        organisation_unit_id = EXCLUDED.organisation_unit_id,
                        name = EXCLUDED.name,
                        status = 'active',
                        updated_at = now()
                """),
                {
                    "id": admin_user_id,
                    "org_unit_id": org_unit_id,
                    "role_id": role_id,
                    "name": admin_name,
                    "email": admin_email,
                },
            )
            admin_user_result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": admin_email},
            )
            admin_user_id = str(admin_user_result.scalar_one())

            # 6. If temporary password provided, configure standalone identity provider and user identity
            if temporary_password:
                idp_id = str(uuid.uuid4())
                await session.execute(
                    text("""
                        INSERT INTO identity_providers (id, name, type, auto_login_enabled, is_active)
                        VALUES (:id, 'Local Authentication', 'standalone', false, true)
                        ON CONFLICT (name) DO NOTHING
                    """),
                    {"id": idp_id},
                )
                idp_result = await session.execute(
                    text(
                        "SELECT id FROM identity_providers WHERE name = 'Local Authentication'"
                    )
                )
                idp_id = str(idp_result.scalar_one())

                password_hash = hash_password(temporary_password)
                identity_id = str(uuid.uuid4())
                await session.execute(
                    text("""
                        INSERT INTO user_identities (id, user_id, identity_provider_id, provider_user_id, password_hash)
                        VALUES (:id, :user_id, :idp_id, :provider_user_id, :password_hash)
                        ON CONFLICT (identity_provider_id, provider_user_id) DO UPDATE SET
                            password_hash = EXCLUDED.password_hash
                    """),
                    {
                        "id": identity_id,
                        "user_id": admin_user_id,
                        "idp_id": idp_id,
                        "provider_user_id": admin_email,
                        "password_hash": password_hash,
                    },
                )

            # 7. Commit everything as a single transaction
            await session.commit()
            print(
                f"✅ Successfully provisioned tenant '{tenant_name}' in schema '{schema_name}'"
            )
            print(f"   Subdomain:       {subdomain}")
            if custom_domain:
                print(f"   Custom Domain:   {custom_domain}")
            print(f"   Hosting Mode:    {hosting_mode}")
            print(
                f"   Tenant Admin:    {admin_email} (User ID: {admin_user_id}, Role ID: {role_id})"
            )
            if temporary_password:
                print("   Password Status: Configured (hashed in user_identities)")
            else:
                print("   Password Status: None set (awaiting IdP or password setup)")

        except Exception as e:
            await session.rollback()
            print(f"❌ Failed to provision tenant: {e}")
            raise
        finally:
            # Ensure the connection goes back to public before returning to the pool
            await session.execute(text("SET search_path TO public"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision a new tenant schema and seed its initial organization structure and admin user."
    )
    parser.add_argument(
        "--subdomain",
        required=True,
        help="Subdomain for the tenant (e.g. 'cbe', 'acme').",
    )
    parser.add_argument(
        "--admin-email",
        required=True,
        help="Email address for the initial tenant administrator.",
    )
    parser.add_argument(
        "--admin-name",
        required=True,
        help="Full name of the initial tenant administrator.",
    )
    parser.add_argument(
        "--temporary-password",
        "--admin-password",
        dest="temporary_password",
        default=None,
        help="Temporary password for the administrator (optional).",
    )
    parser.add_argument(
        "--hosting-mode",
        default="shared",
        choices=["shared", "dedicated"],
        help="Hosting mode: 'shared' (default) or 'dedicated'.",
    )
    parser.add_argument(
        "--custom-domain",
        default=None,
        help="Optional custom domain (e.g. 'portal.example.com').",
    )
    parser.add_argument(
        "--primary-color",
        default=None,
        help="Optional primary brand color in hex (e.g. '#1E40AF').",
    )
    parser.add_argument(
        "--logo-url",
        default=None,
        help="Optional brand logo URL or path.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Display name of the tenant (defaults to formatted subdomain).",
    )
    return parser.parse_args()


# --- CLI Execution ---
async def main() -> None:
    if len(sys.argv) == 1:
        print(
            "Usage: python -m scripts.migration.provision_tenant --subdomain <subdomain> "
            "--admin-email <email> --admin-name <name> [options]\n"
        )
        print("Run with --help to see all available arguments.")
        sys.exit(1)

    args = parse_args()
    await provision_tenant_and_admin(
        subdomain=args.subdomain,
        admin_email=args.admin_email,
        admin_name=args.admin_name,
        temporary_password=args.temporary_password,
        hosting_mode=args.hosting_mode,
        custom_domain=args.custom_domain,
        primary_color=args.primary_color,
        logo_url=args.logo_url,
        name=args.name,
    )


if __name__ == "__main__":
    asyncio.run(main())
