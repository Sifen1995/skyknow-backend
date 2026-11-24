from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.composition.database import get_db
from app.composition.redis import get_redis
from app.config import settings
from app.modules.tenants.application.delete_tenant import DeleteTenant
from app.modules.tenants.application.get_tenant_branding import GetTenantBranding
from app.modules.tenants.application.provision_tenant import ProvisionTenant
from app.modules.tenants.application.upload_tenant_logo import UploadTenantLogo
from app.modules.tenants.infrastructure.schema_provisioner import (
    PostgresTenantSchemaProvisioner,
)
from app.modules.tenants.infrastructure.tenant_cache_cleaner import (
    RedisTenantCacheCleaner,
)
from app.modules.tenants.infrastructure.tenant_sql import (
    SqlAlchemyTenantRepository,
)


def get_provision_tenant_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProvisionTenant:
    return ProvisionTenant(
        tenant_repository=SqlAlchemyTenantRepository(session),
        schema_provisioner=PostgresTenantSchemaProvisioner(session),
    )


def get_tenant_branding_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GetTenantBranding:
    return GetTenantBranding(
        tenant_repository=SqlAlchemyTenantRepository(session),
    )


def get_upload_tenant_logo_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UploadTenantLogo:
    return UploadTenantLogo(
        tenant_repository=SqlAlchemyTenantRepository(session),
        assets_storage_dir=settings.ASSETS_STORAGE_DIR,
        assets_public_url_prefix=settings.ASSETS_PUBLIC_URL_PREFIX,
    )


def get_delete_tenant_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> DeleteTenant:
    return DeleteTenant(
        tenant_repository=SqlAlchemyTenantRepository(session),
        schema_provisioner=PostgresTenantSchemaProvisioner(session),
        assets_storage_dir=settings.ASSETS_STORAGE_DIR,
        cache_cleaner=RedisTenantCacheCleaner(redis),
    )
