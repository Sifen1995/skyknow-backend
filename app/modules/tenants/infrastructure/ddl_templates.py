def get_tenant_schema_ddl() -> str:
    """
    DDL for tenant schemas in Schema-per-Tenant isolation.
    Contains:
      - Unit Types & Organization Units (with path GIST index and FK indexes)
      - Identity Providers (with unique auto-login index and type index)
      - Roles & System Role Enums
      - Users (with fillfactor=80, FK indexes, and unindexed last_login_at/updated_at for HOT updates)
      - User Identities (credentials & MFA)
      - Group Mappings
      - Refresh Tokens (with fillfactor=80, user_id index, and user_refresh_tokens view)
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
