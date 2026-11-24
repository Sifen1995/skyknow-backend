from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.tenants.application.delete_tenant import DeleteTenant
from app.modules.tenants.application.errors import (
    InvalidSubdomainError,
    TenantNotFoundError,
)
from app.modules.tenants.domain.models import Tenant


class FakeTenantRepository:
    def __init__(self) -> None:
        self.tenants: dict[str, Tenant] = {}
        self.deleted_subdomains: list[str] = []

    async def get_by_subdomain(self, subdomain: str) -> Tenant | None:
        return self.tenants.get(subdomain.lower())

    async def delete_tenant(self, *, subdomain: str) -> bool:
        self.deleted_subdomains.append(subdomain.lower())
        return self.tenants.pop(subdomain.lower(), None) is not None


class FakeSchemaProvisioner:
    def __init__(self) -> None:
        self.dropped_schemas: list[str] = []

    async def drop_schema(self, *, subdomain: str) -> None:
        self.dropped_schemas.append(subdomain.lower())


@pytest.mark.asyncio
async def test_delete_tenant_success(tmp_path: Path) -> None:
    repo = FakeTenantRepository()
    provisioner = FakeSchemaProvisioner()
    cache_cleaner = AsyncMock()

    subdomain = "acme"
    tenant = Tenant(
        id=uuid4(),
        name="Acme Corp",
        subdomain=subdomain,
        custom_domain=None,
        hosting_mode="shared",
        primary_color="#123456",
        logo_url=f"/assets/tenants/{subdomain}/logo.png",
        status="active",
    )
    repo.tenants[subdomain] = tenant

    # Create dummy logo file and directory under tmp_path
    tenant_asset_dir = tmp_path / "tenants" / subdomain
    tenant_asset_dir.mkdir(parents=True, exist_ok=True)
    logo_file = tenant_asset_dir / "logo.png"
    logo_file.write_bytes(b"dummy image bytes")
    assert logo_file.exists()

    use_case = DeleteTenant(
        tenant_repository=repo,
        schema_provisioner=provisioner,
        assets_storage_dir=tmp_path,
        cache_cleaner=cache_cleaner,
    )

    await use_case.execute(subdomain=subdomain)

    # 1. DB dropped & deleted
    assert subdomain in provisioner.dropped_schemas
    assert subdomain in repo.deleted_subdomains
    assert subdomain not in repo.tenants

    # 2. Disk assets deleted
    assert not tenant_asset_dir.exists()

    # 3. Redis cache cleared
    cache_cleaner.clear_tenant_cache.assert_awaited_once_with(subdomain=subdomain)


@pytest.mark.asyncio
async def test_delete_tenant_not_found(tmp_path: Path) -> None:
    repo = FakeTenantRepository()
    provisioner = FakeSchemaProvisioner()

    use_case = DeleteTenant(
        tenant_repository=repo,
        schema_provisioner=provisioner,
        assets_storage_dir=tmp_path,
    )

    with pytest.raises(TenantNotFoundError) as exc_info:
        await use_case.execute(subdomain="nonexistent")

    assert "Tenant 'nonexistent' was not found" in str(exc_info.value)
    assert len(provisioner.dropped_schemas) == 0


@pytest.mark.asyncio
async def test_delete_tenant_empty_subdomain_raises(tmp_path: Path) -> None:
    repo = FakeTenantRepository()
    provisioner = FakeSchemaProvisioner()

    use_case = DeleteTenant(
        tenant_repository=repo,
        schema_provisioner=provisioner,
        assets_storage_dir=tmp_path,
    )

    with pytest.raises(InvalidSubdomainError):
        await use_case.execute(subdomain="   ")


@pytest.mark.asyncio
async def test_delete_tenant_succeeds_even_without_logo_dir(tmp_path: Path) -> None:
    repo = FakeTenantRepository()
    provisioner = FakeSchemaProvisioner()

    subdomain = "nologocorp"
    tenant = Tenant(
        id=uuid4(),
        name="No Logo Corp",
        subdomain=subdomain,
        custom_domain=None,
        hosting_mode="shared",
        primary_color=None,
        logo_url=None,
        status="active",
    )
    repo.tenants[subdomain] = tenant

    use_case = DeleteTenant(
        tenant_repository=repo,
        schema_provisioner=provisioner,
        assets_storage_dir=tmp_path,
    )

    await use_case.execute(subdomain=subdomain)

    assert subdomain in provisioner.dropped_schemas
    assert subdomain not in repo.tenants
