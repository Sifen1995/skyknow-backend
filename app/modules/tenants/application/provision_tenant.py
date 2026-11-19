import re

from app.modules.tenants.application.dtos import (
    ProvisionTenantInput,
    ProvisionTenantResult,
)
from app.modules.tenants.application.errors import (
    CustomDomainAlreadyExistsError,
    InvalidSubdomainError,
    InvalidTenantInputError,
    SubdomainAlreadyExistsError,
)
from app.modules.tenants.domain.repository import (
    TenantRepository,
    TenantSchemaProvisioner,
)

RESERVED_SUBDOMAINS = {
    "api",
    "admin",
    "public",
    "app",
    "www",
    "localhost",
    "system",
    "auth",
    "mail",
    "status",
}

SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
HEX_COLOR_PATTERN = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


class ProvisionTenant:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        schema_provisioner: TenantSchemaProvisioner,
    ) -> None:
        self._tenant_repo = tenant_repository
        self._schema_provisioner = schema_provisioner

    async def execute(self, input_dto: ProvisionTenantInput) -> ProvisionTenantResult:
        subdomain = input_dto.subdomain.strip().lower()
        if not subdomain or not SUBDOMAIN_PATTERN.match(subdomain):
            raise InvalidSubdomainError(
                f"Subdomain '{subdomain}' is invalid. Must be lowercase alphanumeric (hyphens allowed), 2-63 characters."
            )

        if subdomain in RESERVED_SUBDOMAINS:
            raise InvalidSubdomainError(
                f"Subdomain '{subdomain}' is reserved and cannot be used."
            )

        admin_email = input_dto.admin_email.strip().lower()
        if not admin_email or "@" not in admin_email:
            raise InvalidTenantInputError("A valid administrator email is required.")

        admin_name = input_dto.admin_name.strip()
        if not admin_name:
            raise InvalidTenantInputError("Administrator name cannot be empty.")

        custom_domain = (
            input_dto.custom_domain.strip().lower() if input_dto.custom_domain else None
        )

        primary_color = (
            input_dto.primary_color.strip() if input_dto.primary_color else None
        )
        if primary_color and not HEX_COLOR_PATTERN.match(primary_color):
            raise InvalidTenantInputError(
                f"Primary color '{primary_color}' is invalid. Must be a valid hex color code (e.g. #1E40AF)."
            )

        logo_url = input_dto.logo_url.strip() if input_dto.logo_url else None

        # Check uniqueness in public registry
        existing_subdomain = await self._tenant_repo.get_by_subdomain(subdomain)
        if existing_subdomain is not None:
            raise SubdomainAlreadyExistsError(
                f"A tenant with subdomain '{subdomain}' already exists."
            )

        if custom_domain:
            existing_custom = await self._tenant_repo.get_by_custom_domain(
                custom_domain
            )
            if existing_custom is not None:
                raise CustomDomainAlreadyExistsError(
                    f"A tenant with custom domain '{custom_domain}' already exists."
                )

        tenant_name = (
            input_dto.name.strip()
            if input_dto.name and input_dto.name.strip()
            else subdomain.replace("_", " ").replace("-", " ").title()
        )

        # 1. Register in public.tenants
        tenant = await self._tenant_repo.create_tenant(
            name=tenant_name,
            subdomain=subdomain,
            custom_domain=custom_domain,
            hosting_mode=input_dto.hosting_mode,
            primary_color=primary_color,
            logo_url=logo_url,
        )

        # 2. Provision dedicated schema, DDL, and initial admin user
        clean_subdomain = re.sub(r"[^a-z0-9]", "_", subdomain).strip("_")
        schema_name = f"tenant_{clean_subdomain}"

        admin_user_id = await self._schema_provisioner.provision_schema(
            subdomain=subdomain,
            admin_name=admin_name,
            admin_email=admin_email,
            temporary_password=input_dto.temporary_password,
        )

        return ProvisionTenantResult(
            tenant_id=tenant.id,
            name=tenant.name,
            subdomain=tenant.subdomain,
            schema_name=schema_name,
            custom_domain=tenant.custom_domain,
            hosting_mode=tenant.hosting_mode,
            admin_user_id=admin_user_id,
            admin_email=admin_email,
            admin_name=admin_name,
            primary_color=tenant.primary_color,
            logo_url=tenant.logo_url,
        )
