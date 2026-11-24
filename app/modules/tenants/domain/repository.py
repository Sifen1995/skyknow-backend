from typing import Protocol
from uuid import UUID

from app.modules.tenants.domain.models import Tenant


class TenantRepository(Protocol):
    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        """Fetch tenant by ID from public schema."""
        ...

    async def get_by_subdomain(self, subdomain: str) -> Tenant | None:
        """Fetch tenant by subdomain from public schema."""
        ...

    async def get_by_custom_domain(self, custom_domain: str) -> Tenant | None:
        """Fetch tenant by custom domain from public schema."""
        ...

    async def get_by_subdomain_or_custom_domain(self, identifier: str) -> Tenant | None:
        """Fetch tenant by either subdomain or custom domain from public schema."""
        ...

    async def update_tenant_logo_url(
        self, *, subdomain: str, logo_url: str
    ) -> Tenant | None:
        """Update logo_url for a tenant in the public schema."""
        ...

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
        """Insert and return a newly registered tenant."""
        ...

    async def delete_tenant(self, *, subdomain: str) -> bool:
        """Delete tenant record from public schema."""
        ...


class TenantSchemaProvisioner(Protocol):
    async def provision_schema(
        self,
        *,
        subdomain: str,
        admin_name: str,
        admin_email: str,
        temporary_password: str | None = None,
    ) -> UUID:
        """
        Create the dedicated schema for the tenant, execute its initial DDL,
        seed the default roles and org units, and create the initial tenant admin user.
        Returns the created admin user's UUID.
        """
        ...

    async def drop_schema(self, *, subdomain: str) -> None:
        """Drop the tenant's dedicated PostgreSQL schema and all its objects."""
        ...


class TenantCacheCleaner(Protocol):
    async def clear_tenant_cache(self, *, subdomain: str) -> None:
        """Clear cached tenant entries (such as roles and sessions) from Redis."""
        ...
