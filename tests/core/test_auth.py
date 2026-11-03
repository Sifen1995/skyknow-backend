from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.composition.identity.wiring import (
    get_authenticate_access_token_use_case,
)
from app.main import app
from app.modules.identity.application.functionality_usecases.authenticate_access_token import (
    AuthenticatedUser,
)
from app.routers.security import require_authenticated_user


class FakeAuthenticateAccessToken:
    def __init__(self, result: AuthenticatedUser | None) -> None:
        self.result = result
        self.access_tokens: list[str] = []

    async def execute(self, access_token: str) -> AuthenticatedUser | None:
        self.access_tokens.append(access_token)
        return self.result


@pytest.mark.asyncio
async def test_auth_dependency_accepts_bearer_access_token() -> None:
    user_id = str(uuid4())
    use_case = FakeAuthenticateAccessToken(AuthenticatedUser(user_id=user_id))
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="signed.jwt.token"
    )

    result = await require_authenticated_user(credentials, use_case)

    assert result == AuthenticatedUser(user_id=user_id)
    assert use_case.access_tokens == ["signed.jwt.token"]


@pytest.mark.asyncio
async def test_auth_dependency_rejects_missing_bearer_token() -> None:
    use_case = FakeAuthenticateAccessToken(None)

    with pytest.raises(HTTPException) as exc_info:
        await require_authenticated_user(None, use_case)

    assert exc_info.value.status_code == 401
    assert use_case.access_tokens == []


def test_routes_are_grouped_as_public_and_secured() -> None:
    async def provide_invalid_access_token_use_case() -> FakeAuthenticateAccessToken:
        return FakeAuthenticateAccessToken(None)

    app.dependency_overrides[get_authenticate_access_token_use_case] = (
        provide_invalid_access_token_use_case
    )
    try:
        client = TestClient(app)
        client.cookies.set("skyknow_session", "legacy-cookie-token")

        assert client.get("/health").status_code == 200
        response = client.get("/api/v1/pages")
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Authentication required"
    finally:
        app.dependency_overrides.pop(get_authenticate_access_token_use_case, None)


def test_openapi_documents_bearer_authentication() -> None:
    schema = app.openapi()

    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert {"HTTPBearer": []} in schema["paths"]["/api/v1/pages"]["get"]["security"]
