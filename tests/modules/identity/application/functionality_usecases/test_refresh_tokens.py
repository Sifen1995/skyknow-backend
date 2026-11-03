import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.modules.identity.application.functionality_usecases import refresh_tokens
from app.modules.identity.application.functionality_usecases.logout import Logout
from app.modules.identity.application.functionality_usecases.refresh_tokens import (
    RefreshTokens,
)
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.models import User
from app.modules.identity.domain.refresh_token_repository import RefreshTokenRecord
from tests.modules.identity.fakes import FakeIdentityRepository


class FakeRefreshTokenRepository:
    def __init__(self, record: RefreshTokenRecord | None) -> None:
        self.record = record
        self.created: list[dict[str, object]] = []
        self.revoked: list[str] = []
        self.revoked_families: list[UUID] = []

    async def create(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        family_id: UUID,
        expires_at: datetime,
    ) -> None:
        self.created.append(
            {
                "token_hash": token_hash,
                "user_id": user_id,
                "family_id": family_id,
                "expires_at": expires_at,
            }
        )

    async def get_for_update(self, token_hash: str) -> RefreshTokenRecord | None:
        return self.record

    async def revoke(self, token_hash: str) -> None:
        self.revoked.append(token_hash)

    async def revoke_family(self, family_id: UUID) -> None:
        self.revoked_families.append(family_id)


def make_user() -> User:
    return User(
        id=uuid4(),
        email="person@example.com",
        full_name="Test Person",
        password_hash="stored-hash",
        status=UserStatus.ACTIVE,
        org_unit_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_preserves_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    family_id = uuid4()
    old_token = "old-refresh-token"
    old_hash = hashlib.sha256(old_token.encode()).hexdigest()
    repository = FakeRefreshTokenRepository(
        RefreshTokenRecord(
            user_id=user.id,
            family_id=family_id,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            revoked_at=None,
        )
    )
    monkeypatch.setattr(refresh_tokens, "token_urlsafe", lambda _: "new-refresh-token")
    monkeypatch.setattr(
        refresh_tokens,
        "create_access_token",
        lambda *_args, **_kwargs: "new-access-token",
    )

    result = await RefreshTokens(
        FakeIdentityRepository(user=user),
        repository,
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=86400,
        jwt_secret_key="test-secret",
        jwt_algorithm="HS256",
    ).execute(old_token)

    assert result.access_token == "new-access-token"
    assert result.refresh_token == "new-refresh-token"
    assert result.expires_in == 900
    assert repository.revoked == [old_hash]
    assert (
        repository.created[0]["token_hash"]
        == hashlib.sha256(b"new-refresh-token").hexdigest()
    )
    assert repository.created[0]["family_id"] == family_id


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token_family() -> None:
    family_id = uuid4()
    repository = FakeRefreshTokenRepository(
        RefreshTokenRecord(
            user_id=uuid4(),
            family_id=family_id,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            revoked_at=None,
        )
    )

    await Logout(repository).execute("refresh-token")

    assert repository.revoked_families == [family_id]
