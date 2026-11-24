from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ProvisionTenantInput:
    subdomain: str
    admin_email: str
    admin_name: str
    name: str | None = None
    temporary_password: str | None = None
    hosting_mode: str = "shared"
    custom_domain: str | None = None
    primary_color: str | None = None
    logo_url: str | None = None


@dataclass(frozen=True)
class ProvisionTenantResult:
    tenant_id: UUID
    name: str
    subdomain: str
    schema_name: str
    custom_domain: str | None
    hosting_mode: str
    admin_user_id: UUID
    admin_email: str
    admin_name: str
    primary_color: str | None = None
    logo_url: str | None = None


@dataclass(frozen=True)
class TenantBrandingResult:
    name: str
    subdomain: str
    custom_domain: str | None
    primary_color: str | None
    logo_url: str | None
