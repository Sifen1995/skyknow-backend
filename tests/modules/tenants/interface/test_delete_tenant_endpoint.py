from fastapi.testclient import TestClient

from app.composition.tenants import get_delete_tenant_use_case
from app.main import app
from app.modules.tenants.application.errors import TenantNotFoundError
from app.routers.security import (
    AuthenticatedPlatformAdmin,
    require_authenticated_platform_admin,
    require_trusted_origin,
)


class FakeDeleteTenantUseCase:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.deleted_subdomain: str | None = None

    async def execute(self, *, subdomain: str) -> None:
        if self.error:
            raise self.error
        self.deleted_subdomain = subdomain


def test_delete_tenant_endpoint_success() -> None:
    fake_use_case = FakeDeleteTenantUseCase()

    app.dependency_overrides[get_delete_tenant_use_case] = lambda: fake_use_case
    app.dependency_overrides[require_authenticated_platform_admin] = lambda: (
        AuthenticatedPlatformAdmin(admin_id="test-super-admin-id")
    )
    app.dependency_overrides[require_trusted_origin] = lambda: None

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/platform-admin/tenants/acme")

        assert response.status_code == 200
        body = response.json()
        assert body["subdomain"] == "acme"
        assert "successfully deleted" in body["message"]
        assert fake_use_case.deleted_subdomain == "acme"
    finally:
        app.dependency_overrides.clear()


def test_delete_tenant_endpoint_not_found() -> None:
    fake_use_case = FakeDeleteTenantUseCase(
        error=TenantNotFoundError("Tenant 'nonexistent' was not found.")
    )

    app.dependency_overrides[get_delete_tenant_use_case] = lambda: fake_use_case
    app.dependency_overrides[require_authenticated_platform_admin] = lambda: (
        AuthenticatedPlatformAdmin(admin_id="test-super-admin-id")
    )
    app.dependency_overrides[require_trusted_origin] = lambda: None

    try:
        client = TestClient(app)
        response = client.delete("/api/v1/platform-admin/tenants/nonexistent")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "tenant_not_found"
    finally:
        app.dependency_overrides.clear()
