from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.identity.domain.models import TenantRefreshToken
from app.modules.identity.infrastructure.tenant_refresh_sql import (
    SqlAlchemyTenantRefreshTokenRepository,
    TenantRefreshTokenStoreError,
)


@pytest.mark.asyncio
async def test_store_refresh_token_adds_entity() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    repo = SqlAlchemyTenantRefreshTokenRepository(session)

    family_id = uuid4()
    user_id = uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=7)

    await repo.store_refresh_token(
        family_id=family_id,
        user_id=user_id,
        secret_hash="a" * 64,
        expires_at=expires_at,
    )

    session.add.assert_called_once()
    added_obj = session.add.call_args[0][0]
    assert isinstance(added_obj, TenantRefreshToken)
    assert added_obj.family_id == family_id
    assert added_obj.user_id == user_id
    assert added_obj.secret_hash == "a" * 64
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_refresh_token_raises_typed_error_on_integrity_violation() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush.side_effect = IntegrityError(
        "statement", {}, Exception("Duplicate key")
    )
    repo = SqlAlchemyTenantRefreshTokenRepository(session)

    with pytest.raises(TenantRefreshTokenStoreError) as exc_info:
        await repo.store_refresh_token(
            family_id=uuid4(),
            user_id=uuid4(),
            secret_hash="a" * 64,
            expires_at=datetime.now(UTC),
        )

    assert "Could not store refresh token" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_refresh_token_returns_record_when_found() -> None:
    family_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    token_entity = MagicMock(spec=TenantRefreshToken)
    token_entity.family_id = family_id
    token_entity.user_id = user_id
    token_entity.current_generation = 1
    token_entity.secret_hash = "hash123"
    token_entity.expires_at = now
    token_entity.revoked_at = None

    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = token_entity

    session = AsyncMock()
    session.execute.return_value = fake_result
    repo = SqlAlchemyTenantRefreshTokenRepository(session)

    record = await repo.get_refresh_token(family_id)

    assert record is not None
    assert record.family_id == family_id
    assert record.user_id == user_id
    assert record.current_generation == 1
    assert record.secret_hash == "hash123"
    assert record.revoked_at is None


@pytest.mark.asyncio
async def test_get_refresh_token_returns_none_when_missing() -> None:
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute.return_value = fake_result
    repo = SqlAlchemyTenantRefreshTokenRepository(session)

    record = await repo.get_refresh_token(uuid4())
    assert record is None


@pytest.mark.asyncio
async def test_rotate_refresh_token_returns_new_generation() -> None:
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = 2

    session = AsyncMock()
    session.execute.return_value = fake_result
    repo = SqlAlchemyTenantRefreshTokenRepository(session)

    new_gen = await repo.rotate_refresh_token(
        family_id=uuid4(),
        new_secret_hash="newhash",
        new_expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    assert new_gen == 2
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_rotate_refresh_token_raises_error_if_not_found_or_revoked() -> None:
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute.return_value = fake_result
    repo = SqlAlchemyTenantRefreshTokenRepository(session)

    with pytest.raises(TenantRefreshTokenStoreError) as exc_info:
        await repo.rotate_refresh_token(
            family_id=uuid4(),
            new_secret_hash="newhash",
            new_expires_at=datetime.now(UTC),
        )

    assert "Refresh token rotation failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_revoke_refresh_token_commits_transaction() -> None:
    session = AsyncMock()
    repo = SqlAlchemyTenantRefreshTokenRepository(session)

    family_id = uuid4()
    await repo.revoke_refresh_token(family_id)

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_all_for_user_flushes_transaction() -> None:
    session = AsyncMock()
    repo = SqlAlchemyTenantRefreshTokenRepository(session)

    user_id = uuid4()
    await repo.revoke_all_for_user(user_id)

    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()
