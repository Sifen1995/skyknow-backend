from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.composition.identity.wiring import (
    get_authenticate_session_use_case,
)
from app.config import settings
from app.main import app
from app.modules.identity.application.functionality_usecases.authenticate_session import (
    AuthenticatedSession,
    AuthenticateSession,
)
from app.routers.security import require_authenticated_user


class FakeAuthenticateSession(AuthenticateSession):
    def __init__(self, result: AuthenticatedSession | None) -> None:
        self.result = result
        self.session_tokens: list[str] = []

    async def execute(self, session_token: str) -> AuthenticatedSession | None:
        self.session_tokens.append(session_token)
        return self.result


def make_request(
    *,
    method: str = "GET",
    cookie: str | None = None,
    origin: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie is not None:
        headers.append((b"cookie", f"skyknow_session={cookie}".encode()))
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    return Request(
        {
            "type": "http",
            "app": FastAPI(),
            "method": method,
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "server": ("test", 80),
            "client": ("test", 1),
        }
    )


@pytest.mark.asyncio
async def test_auth_dependency_accepts_valid_session() -> None:
    user_id = str(uuid4())
    use_case = FakeAuthenticateSession(
        AuthenticatedSession(user_id=user_id, csrf_token="csrf")
    )
    request = make_request(cookie="opaque-session")

    result = await require_authenticated_user(request, use_case)

    assert result == AuthenticatedSession(user_id=user_id, csrf_token="csrf")
    assert use_case.session_tokens == ["opaque-session"]


@pytest.mark.asyncio
async def test_auth_dependency_requires_session_cookie() -> None:
    use_case = FakeAuthenticateSession(None)

    with pytest.raises(HTTPException) as exc_info:
        await require_authenticated_user(make_request(), use_case)

    assert exc_info.value.status_code == 401
    assert use_case.session_tokens == []


@pytest.mark.asyncio
async def test_auth_dependency_checks_csrf_on_state_changing_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "CORS_ALLOWED_ORIGINS", ["https://frontend.test"])
    use_case = FakeAuthenticateSession(
        AuthenticatedSession(
            user_id=str(uuid4()),
            csrf_token="expected-csrf",
        )
    )
    request = make_request(
        method="POST",
        cookie="opaque-session",
        origin="https://frontend.test",
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_authenticated_user(request, use_case, csrf_token="wrong-csrf")

    assert exc_info.value.status_code == 403


def test_routes_are_grouped_as_public_and_secured() -> None:
    async def provide_invalid_session_use_case() -> FakeAuthenticateSession:
        return FakeAuthenticateSession(None)

    app.dependency_overrides[get_authenticate_session_use_case] = (
        provide_invalid_session_use_case
    )
    try:
        client = TestClient(app)

        assert client.get("/health").status_code == 200
        response = client.get("/api/v1/pages")
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "Authentication required"
    finally:
        app.dependency_overrides.pop(get_authenticate_session_use_case, None)


def test_authenticated_session_dependency_is_cached_per_request() -> None:
    authenticated_session = AuthenticatedSession(
        user_id=str(uuid4()),
        csrf_token="csrf-for-test",
    )
    use_case = FakeAuthenticateSession(authenticated_session)

    async def provide_use_case() -> FakeAuthenticateSession:
        return use_case

    app.dependency_overrides[get_authenticate_session_use_case] = provide_use_case
    try:
        client = TestClient(app)
        client.cookies.set("skyknow_session", "opaque-session")
        response = client.get("/api/v1/auth/csrf")

        assert response.status_code == 200
        assert response.json() == {"csrf_token": "csrf-for-test"}
        assert use_case.session_tokens == ["opaque-session"]
    finally:
        app.dependency_overrides.pop(get_authenticate_session_use_case, None)
