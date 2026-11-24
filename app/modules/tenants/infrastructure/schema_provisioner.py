import re
import uuid
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.tenants.application.errors import TenantProvisioningFailedError
from app.modules.tenants.domain.repository import TenantSchemaProvisioner
from app.modules.tenants.infrastructure.ddl_templates import get_tenant_schema_ddl


def generate_schema_name(subdomain: str) -> str:
    clean = re.sub(r"[^a-z0-9]", "_", subdomain.lower()).strip("_")
    return f"tenant_{clean}"


class PostgresTenantSchemaProvisioner(TenantSchemaProvisioner):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def provision_schema(
        self,
        *,
        subdomain: str,
        admin_name: str,
        admin_email: str,
        temporary_password: str | None = None,
    ) -> UUID:
        schema_name = generate_schema_name(subdomain)

        try:
            # 1. Create the Schema
            await self._session.execute(
                text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
            )

            # 2. Execute multi-statement DDL via raw asyncpg driver connection
            conn = await self._session.connection()
            raw_conn = await conn.get_raw_connection()
            ddl_script = (
                f'SET search_path TO "{schema_name}", public;\n'
                + get_tenant_schema_ddl()
            )
            driver_conn = raw_conn.driver_connection
            if driver_conn is None:
                raise TenantProvisioningFailedError(
                    "Failed to obtain raw database connection"
                )
            await driver_conn.execute(ddl_script)

            # Keep search path active for parameterised queries
            await self._session.execute(
                text(f'SET search_path TO "{schema_name}", public')
            )

            # 3. Seed Default Role: admin (company scope)
            role_id = uuid.uuid4()
            await self._session.execute(
                text("""
                    INSERT INTO roles (id, name, scope, description) 
                    VALUES (:id, 'admin', 'company', 'Full Platform Administrator')
                    ON CONFLICT (name, scope) DO NOTHING
                """),
                {"id": role_id},
            )
            role_result = await self._session.execute(
                text("SELECT id FROM roles WHERE name = 'admin' AND scope = 'company'")
            )
            role_id = role_result.scalar_one()

            # 4. Seed Unit Type: Headquarters
            unit_type_id = uuid.uuid4()
            await self._session.execute(
                text("""
                    INSERT INTO unit_types (id, name, level) 
                    VALUES (:id, 'Headquarters', 0)
                    ON CONFLICT (name) DO NOTHING
                """),
                {"id": unit_type_id},
            )
            unit_type_result = await self._session.execute(
                text("SELECT id FROM unit_types WHERE name = 'Headquarters'")
            )
            unit_type_id = unit_type_result.scalar_one()

            # 5. Seed Root Organisation Unit
            org_unit_id = uuid.uuid4()
            await self._session.execute(
                text("""
                    INSERT INTO organisation_units (id, unit_type_id, name, slug, path) 
                    VALUES (:id, :ut_id, 'Headquarters', 'hq', 'hq')
                    ON CONFLICT (path) DO NOTHING
                """),
                {"id": org_unit_id, "ut_id": unit_type_id},
            )
            org_unit_result = await self._session.execute(
                text("SELECT id FROM organisation_units WHERE path = 'hq'")
            )
            org_unit_id = org_unit_result.scalar_one()

            # 6. Create Initial Admin User in users table
            admin_user_id = uuid.uuid4()
            await self._session.execute(
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
            admin_user_result = await self._session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": admin_email},
            )
            raw_id = admin_user_result.scalar_one()
            admin_user_id = raw_id if isinstance(raw_id, UUID) else UUID(str(raw_id))

            # 7. Seed Password Credentials in user_identities if provided
            if temporary_password:
                idp_id = uuid.uuid4()
                await self._session.execute(
                    text("""
                        INSERT INTO identity_providers (id, name, type, auto_login_enabled, is_active)
                        VALUES (:id, 'Local Authentication', 'standalone', false, true)
                        ON CONFLICT (name) DO NOTHING
                    """),
                    {"id": idp_id},
                )
                idp_result = await self._session.execute(
                    text(
                        "SELECT id FROM identity_providers WHERE name = 'Local Authentication'"
                    )
                )
                idp_id = idp_result.scalar_one()

                password_hash = hash_password(temporary_password)
                identity_id = uuid.uuid4()
                await self._session.execute(
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

            return admin_user_id

        except Exception as exc:
            raise TenantProvisioningFailedError(
                f"Failed to provision tenant schema '{schema_name}': {exc}"
            ) from exc
        finally:
            await self._session.execute(text("SET search_path TO public"))

    async def drop_schema(self, *, subdomain: str) -> None:
        schema_name = generate_schema_name(subdomain)
        await self._session.execute(text("SET search_path TO public"))
        await self._session.execute(
            text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
        )
