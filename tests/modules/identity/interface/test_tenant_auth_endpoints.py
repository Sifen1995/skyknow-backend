from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.composition.identity import (
    TenantContext,
    get_tenant_context,
    get_tenant_login_use_case,
    get_tenant_logout_use_case,
    get_tenant_refresh_use_case,
)
from app.main import app
from app.modules.identity.application.dtos import (
    TenantLoginRequest,
    TenantLoginResult,
    TenantLogoutRequest,
    TenantRefreshRequest,
    TenantRefreshResult,
    TenantUserProfile,
)
from app.modules.identity.application.errors import (
    TenantAuthenticationFailedError,
    TenantRefreshTokenInvalidError,
    TenantUserDisabledError,
)
from app.routers.security import require_trusted_origin


class FakeTenantLogin:
    def __init__(
        self,
        result: TenantLoginResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.last_subdomain: str | None = None

    async def execute(
        self, request: TenantLoginRequest, *, subdomain: str
    ) -> TenantLoginResult:
        self.last_subdomain = subdomain
        if self.error:
            raise self.error
        assert self.result is not None
        return self.result


class FakeTenantRefreshTokenUseCase:
    def __init__(
        self,
        result: TenantRefreshResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error

    async def execute(
        self, request: TenantRefreshRequest, *, subdomain: str
    ) -> TenantRefreshResult:
        if self.error:
            raise self.error
        assert self.result is not None
        return self.result


class FakeTenantLogout:
    def __init__(self) -> None:
        self.invoked = False
        self.last_family_id: UUID | None = None

    async def execute(self, request: TenantLogoutRequest) -> None:
        self.invoked = True
        self.last_family_id = request.family_id


@pytest.fixture
def fake_tenant_context() -> TenantContext:
    return TenantContext(
        subdomain="acme",
        schema_name="tenant_acme",
        session=None,  # type: ignore[arg-type]
    )


def test_tenant_admin_login_endpoint_success(
    fake_tenant_context: TenantContext,
) -> None:
    user_id = uuid4()
    org_unit_id = uuid4()
    family_id = uuid4()

    expected_profile = TenantUserProfile(
        id=user_id,
        name="Acme Admin",
        email="admin@acme.com",
        role="admin",
        organisation_unit_id=org_unit_id,
        status="active",
        is_admin=True,
    )
    expected_result = TenantLoginResult(
        user=expected_profile,
        access_token="test.jwt.access",
        refresh_token="test.raw.refresh",
        family_id=family_id,
        current_generation=1,
        expires_in=900,
    )
    fake_login = FakeTenantLogin(result=expected_result)

    app.dependency_overrides[get_tenant_context] = lambda: fake_tenant_context
    app.dependency_overrides[get_tenant_login_use_case] = lambda: fake_login
    app.dependency_overrides[require_trusted_origin] = lambda: None

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/identity/login",
            json={"email": "admin@acme.com", "password": "SecurePassword123!"},
            headers={"X-Tenant-Subdomain": "acme"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "test.jwt.access"
        assert body["refresh_token"] == "test.raw.refresh"
        assert body["family_id"] == str(family_id)
        assert body["current_generation"] == 1
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "admin@acme.com"
        assert body["user"]["role"] == "admin"
        assert body["user"]["is_admin"] is True
        assert fake_login.last_subdomain == "acme"
    finally:
        app.dependency_overrides.clear()


def test_tenant_regular_user_login_endpoint_success(
    fake_tenant_context: TenantContext,
) -> None:
    user_id = uuid4()
    org_unit_id = uuid4()
    family_id = uuid4()

    expected_profile = TenantUserProfile(
        id=user_id,
        name="Acme Author",
        email="author@acme.com",
        role="author",
        organisation_unit_id=org_unit_id,
        status="active",
        is_admin=False,
    )
    expected_result = TenantLoginResult(
        user=expected_profile,
        access_token="test.jwt.access",
        refresh_token="test.raw.refresh",
        family_id=family_id,
        current_generation=1,
        expires_in=900,
    )
    fake_login = FakeTenantLogin(result=expected_result)

    app.dependency_overrides[get_tenant_context] = lambda: fake_tenant_context
    app.dependency_overrides[get_tenant_login_use_case] = lambda: fake_login
    app.dependency_overrides[require_trusted_origin] = lambda: None

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/identity/login",
            json={"email": "author@acme.com", "password": "AuthorPassword123!"},
            headers={"X-Tenant-Subdomain": "acme"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["user"]["role"] == "author"
        assert body["user"]["is_admin"] is False
    finally:
        app.dependency_overrides.clear()


def test_tenant_login_endpoint_invalid_credentials(
    fake_tenant_context: TenantContext,
) -> None:
    fake_login = FakeTenantLogin(
        error=TenantAuthenticationFailedError("Invalid email or password")
    )

    app.dependency_overrides[get_tenant_context] = lambda: fake_tenant_context
    app.dependency_overrides[get_tenant_login_use_case] = lambda: fake_login
    app.dependency_overrides[require_trusted_origin] = lambda: None

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/identity/login",
            json={"email": "admin@acme.com", "password": "WrongPassword"},
            headers={"X-Tenant-Subdomain": "acme"},
        )

        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Invalid email or password"
    finally:
        app.dependency_overrides.clear()


def test_tenant_login_endpoint_disabled_user(
    fake_tenant_context: TenantContext,
) -> None:
    fake_login = FakeTenantLogin(
        error=TenantUserDisabledError("Your user account has been disabled")
    )

    app.dependency_overrides[get_tenant_context] = lambda: fake_tenant_context
    app.dependency_overrides[get_tenant_login_use_case] = lambda: fake_login
    app.dependency_overrides[require_trusted_origin] = lambda: None

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/identity/login",
            json={"email": "user@acme.com", "password": "UserPassword123!"},
            headers={"X-Tenant-Subdomain": "acme"},
        )

        assert response.status_code == 403
        assert (
            response.json()["error"]["message"] == "Your user account has been disabled"
        )
    finally:
        app.dependency_overrides.clear()


def test_tenant_refresh_endpoint_success(
    fake_tenant_context: TenantContext,
) -> None:
    family_id = uuid4()
    expected_result = TenantRefreshResult(
        access_token="new.jwt.access",
        refresh_token="new.raw.refresh",
        family_id=family_id,
        current_generation=2,
        expires_in=900,
    )
    fake_refresh = FakeTenantRefreshTokenUseCase(result=expected_result)

    app.dependency_overrides[get_tenant_context] = lambda: fake_tenant_context
    app.dependency_overrides[get_tenant_refresh_use_case] = lambda: fake_refresh
    app.dependency_overrides[require_trusted_origin] = lambda: None

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/identity/refresh",
            json={
                "family_id": str(family_id),
                "count": 1,
                "refresh_token": "current.refresh.token",
            },
            headers={"X-Tenant-Subdomain": "acme"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "new.jwt.access"
        assert body["refresh_token"] == "new.raw.refresh"
        assert body["family_id"] == str(family_id)
        assert body["current_generation"] == 2
    finally:
        app.dependency_overrides.clear()


def test_tenant_refresh_endpoint_rejected_theft(
    fake_tenant_context: TenantContext,
) -> None:
    family_id = uuid4()
    fake_refresh = FakeTenantRefreshTokenUseCase(
        error=TenantRefreshTokenInvalidError("Refresh token is invalid or expired")
    )

    app.dependency_overrides[get_tenant_context] = lambda: fake_tenant_context
    app.dependency_overrides[get_tenant_refresh_use_case] = lambda: fake_refresh
    app.dependency_overrides[require_trusted_origin] = lambda: None

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/identity/refresh",
            json={
                "family_id": str(family_id),
                "count": 1,
                "refresh_token": "reused.token",
            },
            headers={"X-Tenant-Subdomain": "acme"},
        )

        assert response.status_code == 401
        assert (
            response.json()["error"]["message"] == "Refresh token is invalid or expired"
        )
    finally:
        app.dependency_overrides.clear()


def test_tenant_logout_endpoint_success(
    fake_tenant_context: TenantContext,
) -> None:
    family_id = uuid4()
    fake_logout = FakeTenantLogout()

    app.dependency_overrides[get_tenant_context] = lambda: fake_tenant_context
    app.dependency_overrides[get_tenant_logout_use_case] = lambda: fake_logout

    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/identity/logout",
            json={"family_id": str(family_id)},
            headers={"X-Tenant-Subdomain": "acme"},
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"
        assert fake_logout.invoked is True
        assert fake_logout.last_family_id == family_id
    finally:
        app.dependency_overrides.clear()
