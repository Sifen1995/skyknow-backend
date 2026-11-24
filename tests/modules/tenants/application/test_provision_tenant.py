import uuid
from uuid import UUID

import pytest

from app.modules.tenants.application.dtos import ProvisionTenantInput
from app.modules.tenants.application.errors import (
    CustomDomainAlreadyExistsError,
    InvalidSubdomainError,
    InvalidTenantInputError,
    SubdomainAlreadyExistsError,
    TenantNotFoundError,
)
from app.modules.tenants.application.get_tenant_branding import GetTenantBranding
from app.modules.tenants.application.provision_tenant import ProvisionTenant
from app.modules.tenants.application.upload_tenant_logo import UploadTenantLogo
from app.modules.tenants.domain.models import Tenant


class InMemoryTenantRepository:
    def __init__(self) -> None:
        self.tenants_by_subdomain: dict[str, Tenant] = {}
        self.tenants_by_custom_domain: dict[str, Tenant] = {}

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        return None

    async def get_by_subdomain(self, subdomain: str) -> Tenant | None:
        return self.tenants_by_subdomain.get(subdomain)

    async def get_by_custom_domain(self, custom_domain: str) -> Tenant | None:
        return self.tenants_by_custom_domain.get(custom_domain)

    async def get_by_subdomain_or_custom_domain(self, identifier: str) -> Tenant | None:
        return self.tenants_by_subdomain.get(
            identifier
        ) or self.tenants_by_custom_domain.get(identifier)

    async def update_tenant_logo_url(
        self, *, subdomain: str, logo_url: str
    ) -> Tenant | None:
        tenant = self.tenants_by_subdomain.get(subdomain)
        if tenant is None:
            return None
        tenant.logo_url = logo_url
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
        self.tenants_by_subdomain[subdomain] = tenant
        if custom_domain:
            self.tenants_by_custom_domain[custom_domain] = tenant
        return tenant

    async def delete_tenant(self, *, subdomain: str) -> bool:
        tenant = self.tenants_by_subdomain.pop(subdomain, None)
        if tenant and tenant.custom_domain:
            self.tenants_by_custom_domain.pop(tenant.custom_domain, None)
        return tenant is not None


class InMemorySchemaProvisioner:
    def __init__(self) -> None:
        self.provisioned_schemas: list[dict[str, object]] = []
        self.dropped_schemas: list[str] = []

    async def drop_schema(self, *, subdomain: str) -> None:
        self.dropped_schemas.append(subdomain)

    async def provision_schema(
        self,
        *,
        subdomain: str,
        admin_name: str,
        admin_email: str,
        temporary_password: str | None = None,
    ) -> UUID:
        admin_id = uuid.uuid4()
        self.provisioned_schemas.append(
            {
                "subdomain": subdomain,
                "admin_name": admin_name,
                "admin_email": admin_email,
                "temporary_password": temporary_password,
                "admin_id": admin_id,
            }
        )
        return admin_id


@pytest.mark.asyncio
async def test_provision_tenant_success() -> None:
    repo = InMemoryTenantRepository()
    provisioner = InMemorySchemaProvisioner()
    use_case = ProvisionTenant(tenant_repository=repo, schema_provisioner=provisioner)

    input_dto = ProvisionTenantInput(
        subdomain="acme",
        admin_email="admin@acme.com",
        admin_name="Acme Admin",
        temporary_password="SecretPassword123!",
        custom_domain="portal.acme.com",
    )

    result = await use_case.execute(input_dto)

    assert result.subdomain == "acme"
    assert result.schema_name == "tenant_acme"
    assert result.name == "Acme"
    assert result.admin_email == "admin@acme.com"
    assert result.custom_domain == "portal.acme.com"
    assert len(provisioner.provisioned_schemas) == 1
    assert provisioner.provisioned_schemas[0]["subdomain"] == "acme"


@pytest.mark.asyncio
async def test_provision_tenant_rejects_invalid_subdomain() -> None:
    repo = InMemoryTenantRepository()
    provisioner = InMemorySchemaProvisioner()
    use_case = ProvisionTenant(tenant_repository=repo, schema_provisioner=provisioner)

    input_dto = ProvisionTenantInput(
        subdomain="invalid_subdomain!",
        admin_email="admin@acme.com",
        admin_name="Acme Admin",
    )

    with pytest.raises(InvalidSubdomainError):
        await use_case.execute(input_dto)


@pytest.mark.asyncio
async def test_provision_tenant_rejects_reserved_subdomain() -> None:
    repo = InMemoryTenantRepository()
    provisioner = InMemorySchemaProvisioner()
    use_case = ProvisionTenant(tenant_repository=repo, schema_provisioner=provisioner)

    input_dto = ProvisionTenantInput(
        subdomain="api",
        admin_email="admin@acme.com",
        admin_name="Acme Admin",
    )

    with pytest.raises(InvalidSubdomainError, match="reserved"):
        await use_case.execute(input_dto)


@pytest.mark.asyncio
async def test_provision_tenant_rejects_duplicate_subdomain() -> None:
    repo = InMemoryTenantRepository()
    provisioner = InMemorySchemaProvisioner()
    use_case = ProvisionTenant(tenant_repository=repo, schema_provisioner=provisioner)

    await repo.create_tenant(name="Acme", subdomain="acme")

    input_dto = ProvisionTenantInput(
        subdomain="acme",
        admin_email="admin@acme.com",
        admin_name="Acme Admin",
    )

    with pytest.raises(SubdomainAlreadyExistsError):
        await use_case.execute(input_dto)


@pytest.mark.asyncio
async def test_provision_tenant_rejects_duplicate_custom_domain() -> None:
    repo = InMemoryTenantRepository()
    provisioner = InMemorySchemaProvisioner()
    use_case = ProvisionTenant(tenant_repository=repo, schema_provisioner=provisioner)

    await repo.create_tenant(
        name="Acme", subdomain="acme", custom_domain="portal.acme.com"
    )

    input_dto = ProvisionTenantInput(
        subdomain="acme-corp",
        admin_email="admin@acme.com",
        admin_name="Acme Admin",
        custom_domain="portal.acme.com",
    )

    with pytest.raises(CustomDomainAlreadyExistsError):
        await use_case.execute(input_dto)


@pytest.mark.asyncio
async def test_provision_tenant_with_primary_color_and_logo() -> None:
    repo = InMemoryTenantRepository()
    provisioner = InMemorySchemaProvisioner()
    use_case = ProvisionTenant(tenant_repository=repo, schema_provisioner=provisioner)

    input_dto = ProvisionTenantInput(
        subdomain="cbe",
        admin_email="admin@cbe.et",
        admin_name="CBE Admin",
        primary_color="#9333EA",
        logo_url="https://cbe.et/logo.png",
    )

    result = await use_case.execute(input_dto)
    assert result.primary_color == "#9333EA"
    assert result.logo_url == "https://cbe.et/logo.png"

    # Verify GetTenantBranding
    branding_use_case = GetTenantBranding(tenant_repository=repo)
    branding = await branding_use_case.execute("cbe")
    assert branding.primary_color == "#9333EA"
    assert branding.logo_url == "https://cbe.et/logo.png"
    assert branding.name == "Cbe"


@pytest.mark.asyncio
async def test_provision_tenant_rejects_invalid_primary_color() -> None:
    repo = InMemoryTenantRepository()
    provisioner = InMemorySchemaProvisioner()
    use_case = ProvisionTenant(tenant_repository=repo, schema_provisioner=provisioner)

    input_dto = ProvisionTenantInput(
        subdomain="cbe",
        admin_email="admin@cbe.et",
        admin_name="CBE Admin",
        primary_color="invalid-color-code",
    )

    with pytest.raises(InvalidTenantInputError):
        await use_case.execute(input_dto)


@pytest.mark.asyncio
async def test_get_tenant_branding_not_found() -> None:
    repo = InMemoryTenantRepository()
    branding_use_case = GetTenantBranding(tenant_repository=repo)

    with pytest.raises(TenantNotFoundError):
        await branding_use_case.execute("nonexistent")


@pytest.mark.asyncio
async def test_upload_tenant_logo_success(tmp_path: pytest.TempPathFactory) -> None:
    repo = InMemoryTenantRepository()
    await repo.create_tenant(name="CBE", subdomain="cbe")

    upload_use_case = UploadTenantLogo(
        tenant_repository=repo,
        assets_storage_dir=str(tmp_path),
        assets_public_url_prefix="/assets",
    )

    fake_png_bytes = b"\x89PNG\r\n\x1a\nfakeimagebytes"
    public_url = await upload_use_case.execute(
        subdomain="cbe",
        file_bytes=fake_png_bytes,
        content_type="image/png",
        filename="logo.png",
    )

    assert public_url == "/assets/tenants/cbe/logo.png"

    # Verify file was written to disk
    written_file = tmp_path / "tenants" / "cbe" / "logo.png"
    assert written_file.exists()
    assert written_file.read_bytes() == fake_png_bytes

    # Verify database was updated
    tenant = await repo.get_by_subdomain("cbe")
    assert tenant is not None
    assert tenant.logo_url == "/assets/tenants/cbe/logo.png"


@pytest.mark.asyncio
async def test_upload_tenant_logo_rejects_invalid_mime(
    tmp_path: pytest.TempPathFactory,
) -> None:
    repo = InMemoryTenantRepository()
    await repo.create_tenant(name="CBE", subdomain="cbe")

    upload_use_case = UploadTenantLogo(
        tenant_repository=repo,
        assets_storage_dir=str(tmp_path),
        assets_public_url_prefix="/assets",
    )

    with pytest.raises(InvalidTenantInputError):
        await upload_use_case.execute(
            subdomain="cbe",
            file_bytes=b"executable content",
            content_type="application/x-msdownload",
            filename="malicious.exe",
        )


@pytest.mark.asyncio
async def test_upload_tenant_logo_rejects_oversized_file(
    tmp_path: pytest.TempPathFactory,
) -> None:
    repo = InMemoryTenantRepository()
    await repo.create_tenant(name="CBE", subdomain="cbe")

    upload_use_case = UploadTenantLogo(
        tenant_repository=repo,
        assets_storage_dir=str(tmp_path),
        assets_public_url_prefix="/assets",
    )

    oversized_bytes = b"x" * (3 * 1024 * 1024)  # 3MB > 2MB limit
    with pytest.raises(InvalidTenantInputError):
        await upload_use_case.execute(
            subdomain="cbe",
            file_bytes=oversized_bytes,
            content_type="image/png",
            filename="huge.png",
        )
