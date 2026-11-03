from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.identity.application.errors import AuthenticationFailedError
from app.modules.identity.application.functionality_usecases import (
    login as login_module,
)
from app.modules.identity.application.functionality_usecases.login import Login
from app.modules.identity.application.validation.auth import IdentityInputError
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.models import User
from app.modules.identity.domain.refresh_token_repository import RefreshTokenRecord
from app.modules.identity.interface.schemas import LoginRequest
from tests.modules.identity.fakes import FakeIdentityRepository


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.created_token: dict[str, object] | None = None

    async def create(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        family_id: UUID,
        expires_at: datetime,
    ) -> None:
        self.created_token = {
            "token_hash": token_hash,
            "user_id": user_id,
            "family_id": family_id,
            "expires_at": expires_at,
        }

    async def get_for_update(self, token_hash: str) -> RefreshTokenRecord | None:
        return None

    async def revoke(self, token_hash: str) -> None:
        return None

    async def revoke_family(self, family_id: UUID) -> None:
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
async def test_login_issues_token_pair_and_updates_last_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    identity_repository = FakeIdentityRepository(user=user)
    refresh_token_repository = FakeRefreshTokenRepository()

    monkeypatch.setattr(login_module, "verify_password", lambda *_: True)
    monkeypatch.setattr(login_module, "token_urlsafe", lambda _: "opaque-refresh-token")
    monkeypatch.setattr(
        login_module,
        "create_access_token",
        lambda *_args, **_kwargs: "jwt-token",
    )

    result = await Login(
        identity_repository,
        refresh_token_repository,
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86400,
        jwt_secret_key="test-secret",
        jwt_algorithm="HS256",
    ).execute(LoginRequest(email="  person@example.com  ", password="correct-password"))

    assert result.user is user
    assert result.access_token == "jwt-token"
    assert result.refresh_token == "opaque-refresh-token"
    assert result.expires_in == 900
    assert identity_repository.looked_up_emails == ["person@example.com"]
    assert identity_repository.last_login_update is user
    assert identity_repository.last_login_at is not None
    assert identity_repository.last_login_at.utcoffset() == UTC.utcoffset(
        identity_repository.last_login_at
    )
    assert refresh_token_repository.created_token is not None
    assert refresh_token_repository.created_token["token_hash"] != "opaque-refresh-token"
    assert refresh_token_repository.created_token["user_id"] == user.id
    assert refresh_token_repository.created_token["expires_at"] > identity_repository.last_login_at


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
    refresh_token_repository = FakeRefreshTokenRepository()
    monkeypatch.setattr(
        login_module,
        "verify_password",
        lambda *_: password_matches,
    )

    with pytest.raises(AuthenticationFailedError):
        await Login(
            identity_repository,
            refresh_token_repository,
            access_token_ttl_seconds=900,
            refresh_token_ttl_seconds=86400,
            jwt_secret_key="test-secret",
            jwt_algorithm="HS256",
        ).execute(LoginRequest(email="person@example.com", password="correct-password"))

    assert identity_repository.last_login_update is None
    assert refresh_token_repository.created_token is None


@pytest.mark.asyncio
async def test_login_rejects_invalid_email() -> None:
    refresh_token_repository = FakeRefreshTokenRepository()

    with pytest.raises(IdentityInputError):
        await Login(
            FakeIdentityRepository(),
            refresh_token_repository,
            access_token_ttl_seconds=900,
            refresh_token_ttl_seconds=86400,
            jwt_secret_key="test-secret",
            jwt_algorithm="HS256",
        ).execute(LoginRequest(email="not-an-email", password="correct-password"))

    assert refresh_token_repository.created_token is None
