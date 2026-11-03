from datetime import UTC
from uuid import uuid4

import pytest

from app.modules.identity.application.errors import AuthenticationFailedError
from app.modules.identity.application.functionality_usecases import (
    login as login_module,
)
from app.modules.identity.application.functionality_usecases.login import Login
from app.modules.identity.application.validation.auth import IdentityInputError
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.models import User
from app.modules.identity.domain.redis_repository import SessionRecord
from app.modules.identity.interface.schemas import LoginRequest
from tests.modules.identity.fakes import FakeIdentityRepository


class FakeSessionRepository:
    def __init__(self) -> None:
        self.created_session: dict[str, object] | None = None

    async def create(
        self,
        session_token: str,
        user_id: str,
        csrf_token: str,
        ttl_seconds: int,
    ) -> None:
        self.created_session = {
            "session_token": session_token,
            "user_id": user_id,
            "csrf_token": csrf_token,
            "ttl_seconds": ttl_seconds,
        }

    async def get(self, session_token: str) -> SessionRecord | None:
        return None

    async def revoke(self, session_token: str) -> None:
        return None


def make_user(
    *,
    status: UserStatus = UserStatus.ACTIVE,
    password_hash: str | None = "stored-hash",
) -> User:
    return User(
        id=uuid4(),
        email="person@example.com",
        full_name="Test Person",
        password_hash=password_hash,
        status=status,
        org_unit_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_login_creates_session_and_updates_last_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    identity_repository = FakeIdentityRepository(user=user)
    session_repository = FakeSessionRepository()

    monkeypatch.setattr(login_module, "verify_password", lambda *_: True)
    monkeypatch.setattr(login_module, "token_urlsafe", lambda _: "opaque-token")

    result = await Login(
        identity_repository,
        session_repository,
        session_ttl_seconds=900,
    ).execute(LoginRequest(email="  person@example.com  ", password="correct-password"))

    assert result.user is user
    assert result.session_token == "opaque-token"
    assert result.csrf_token == "opaque-token"
    assert identity_repository.looked_up_emails == ["person@example.com"]
    assert identity_repository.last_login_update is user
    assert identity_repository.last_login_at is not None
    assert identity_repository.last_login_at.utcoffset() == UTC.utcoffset(
        identity_repository.last_login_at
    )
    assert session_repository.created_session == {
        "session_token": "opaque-token",
        "user_id": str(user.id),
        "csrf_token": "opaque-token",
        "ttl_seconds": 900,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user", "password_matches"),
    [
        (None, False),
        (make_user(status=UserStatus.DISABLED), True),
        (make_user(password_hash=None), True),
        (make_user(), False),
    ],
)
async def test_login_rejects_invalid_credentials_or_user_state(
    monkeypatch: pytest.MonkeyPatch,
    user: User | None,
    password_matches: bool,
) -> None:
    identity_repository = FakeIdentityRepository(user=user)
    session_repository = FakeSessionRepository()
    monkeypatch.setattr(
        login_module,
        "verify_password",
        lambda *_: password_matches,
    )

    with pytest.raises(AuthenticationFailedError):
        await Login(
            identity_repository,
            session_repository,
            session_ttl_seconds=900,
        ).execute(LoginRequest(email="person@example.com", password="correct-password"))

    assert identity_repository.last_login_update is None
    assert session_repository.created_session is None


@pytest.mark.asyncio
async def test_login_rejects_invalid_email() -> None:
    session_repository = FakeSessionRepository()

    with pytest.raises(IdentityInputError):
        await Login(
            FakeIdentityRepository(),
            session_repository,
            session_ttl_seconds=900,
        ).execute(LoginRequest(email="not-an-email", password="correct-password"))

    assert session_repository.created_session is None
