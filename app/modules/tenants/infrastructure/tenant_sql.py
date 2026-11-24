import uuid
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenants.domain.models import Tenant
from app.modules.tenants.domain.repository import TenantRepository


class SqlAlchemyTenantRepository(TenantRepository):
    _table_checked: bool = False

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _ensure_table_exists(self) -> None:
        if not SqlAlchemyTenantRepository._table_checked:
            conn = await self._session.connection()
            raw_conn = await conn.get_raw_connection()
            driver_conn = raw_conn.driver_connection
            if driver_conn is not None:
                await driver_conn.execute("""
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
            SqlAlchemyTenantRepository._table_checked = True

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        await self._ensure_table_exists()
        result = await self._session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_subdomain(self, subdomain: str) -> Tenant | None:
        await self._ensure_table_exists()
        result = await self._session.execute(
            select(Tenant).where(Tenant.subdomain == subdomain)
        )
        return result.scalar_one_or_none()

    async def get_by_custom_domain(self, custom_domain: str) -> Tenant | None:
        await self._ensure_table_exists()
        result = await self._session.execute(
            select(Tenant).where(Tenant.custom_domain == custom_domain)
        )
        return result.scalar_one_or_none()

    async def get_by_subdomain_or_custom_domain(self, identifier: str) -> Tenant | None:
        await self._ensure_table_exists()
        result = await self._session.execute(
            select(Tenant).where(
                or_(
                    Tenant.subdomain == identifier.lower(),
                    Tenant.custom_domain == identifier.lower(),
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_tenant_logo_url(
        self, *, subdomain: str, logo_url: str
    ) -> Tenant | None:
        await self._ensure_table_exists()
        tenant = await self.get_by_subdomain(subdomain)
        if tenant is None:
            return None
        tenant.logo_url = logo_url
        await self._session.flush()
        return tenant

    async def create_tenant(
        self,
        *,
        name: str,
        subdomain: str,
        custom_domain: str | None = None,
        hosting_mode: str = "shared",
        primary_color: str | None = None,
        logo_url: str | None = None,
    ) -> Tenant:
        await self._ensure_table_exists()
        tenant = Tenant(
            id=uuid.uuid4(),
            name=name,
            subdomain=subdomain,
            custom_domain=custom_domain,
            hosting_mode=hosting_mode,
            primary_color=primary_color,
            logo_url=logo_url,
            status="active",
        )
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def delete_tenant(self, *, subdomain: str) -> bool:
        await self._ensure_table_exists()
        tenant = await self.get_by_subdomain(subdomain)
        if tenant is None:
            return False
        await self._session.delete(tenant)
        await self._session.flush()
        return True
