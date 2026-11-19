from app.modules.tenants.application.dtos import TenantBrandingResult
from app.modules.tenants.application.errors import TenantNotFoundError
from app.modules.tenants.domain.repository import TenantRepository


class GetTenantBranding:
    def __init__(self, tenant_repository: TenantRepository) -> None:
        self._tenant_repo = tenant_repository

    async def execute(self, identifier: str) -> TenantBrandingResult:
        clean_identifier = identifier.strip().lower()
        tenant = await self._tenant_repo.get_by_subdomain_or_custom_domain(
            clean_identifier
        )
        if tenant is None or tenant.status != "active":
            raise TenantNotFoundError(f"Tenant '{identifier}' was not found.")

        return TenantBrandingResult(
            name=tenant.name,
            subdomain=tenant.subdomain,
            custom_domain=tenant.custom_domain,
            primary_color=tenant.primary_color,
            logo_url=tenant.logo_url,
        )
