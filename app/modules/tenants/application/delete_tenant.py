import logging
import shutil
from pathlib import Path

from app.modules.tenants.application.errors import (
    InvalidSubdomainError,
    TenantNotFoundError,
)
from app.modules.tenants.domain.repository import (
    TenantCacheCleaner,
    TenantRepository,
    TenantSchemaProvisioner,
)

logger = logging.getLogger(__name__)


class DeleteTenant:
    """Use case to completely delete a tenant.

    Performs:
      1. Verification of tenant existence.
      2. Dropping the dedicated PostgreSQL tenant schema (and all its tables/objects).
      3. Deleting the tenant record from public.tenants table.
      4. Deleting the uploaded logo and asset directory from disk (served by Nginx).
      5. Invalidating cached tenant keys from Redis.
    """

    def __init__(
        self,
        tenant_repository: TenantRepository,
        schema_provisioner: TenantSchemaProvisioner,
        assets_storage_dir: Path | str,
        cache_cleaner: TenantCacheCleaner | None = None,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._schema_provisioner = schema_provisioner
        self._assets_storage_dir = Path(assets_storage_dir)
        self._cache_cleaner = cache_cleaner

    async def execute(self, *, subdomain: str) -> None:
        clean_subdomain = subdomain.strip().lower()
        if not clean_subdomain:
            raise InvalidSubdomainError("Subdomain must not be empty.")

        tenant = await self._tenant_repo.get_by_subdomain(clean_subdomain)
        if tenant is None:
            raise TenantNotFoundError(f"Tenant '{clean_subdomain}' was not found.")

        # 1. Drop the dedicated tenant schema in PostgreSQL
        await self._schema_provisioner.drop_schema(subdomain=clean_subdomain)

        # 2. Delete the tenant row from public.tenants
        await self._tenant_repo.delete_tenant(subdomain=clean_subdomain)

        # 3. Delete uploaded logo and tenant asset directory from disk (served by Nginx)
        tenant_asset_dir = self._assets_storage_dir / "tenants" / clean_subdomain
        if tenant_asset_dir.exists():
            try:
                shutil.rmtree(tenant_asset_dir, ignore_errors=True)
                logger.info(
                    "Deleted asset directory '%s' for tenant '%s'",
                    tenant_asset_dir,
                    clean_subdomain,
                )
            except OSError as exc:
                logger.warning(
                    "Failed to delete asset directory '%s': %s",
                    tenant_asset_dir,
                    exc,
                )

        # 4. Invalidate Redis cache if cleaner is configured
        if self._cache_cleaner is not None:
            await self._cache_cleaner.clear_tenant_cache(subdomain=clean_subdomain)
