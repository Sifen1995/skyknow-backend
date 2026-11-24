from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.identity.domain.models import (
    User,
    UserIdentity,
)
from app.modules.identity.infrastructure.tenant_user_sql import (
    SqlAlchemyTenantIdentityRepository,
    SqlAlchemyTenantUserRepository,
)


@pytest.mark.asyncio
async def test_get_by_email_returns_user() -> None:
    user_id = uuid4()
    email = "admin@example.com"

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.email = email
    mock_user.name = "Test Admin"

    fake_result = MagicMock()
    fake_result.unique.return_value.scalar_one_or_none.return_value = mock_user

    session = AsyncMock()
    session.execute.return_value = fake_result
    repo = SqlAlchemyTenantUserRepository(session)

    user = await repo.get_by_email(email)

    assert user is not None
    assert user.id == user_id
    assert user.email == email


@pytest.mark.asyncio
async def test_get_by_id_returns_user() -> None:
    user_id = uuid4()
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id

    fake_result = MagicMock()
    fake_result.unique.return_value.scalar_one_or_none.return_value = mock_user

    session = AsyncMock()
    session.execute.return_value = fake_result
    repo = SqlAlchemyTenantUserRepository(session)

    user = await repo.get_by_id(user_id)

    assert user is not None
    assert user.id == user_id


@pytest.mark.asyncio
async def test_update_last_login_modifies_user_and_flushes() -> None:
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()
    mock_user.last_login_at = None

    session = AsyncMock()
    repo = SqlAlchemyTenantUserRepository(session)

    now = datetime.now(UTC)
    await repo.update_last_login(mock_user, now)

    assert mock_user.last_login_at == now
    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_standalone_identity_returns_identity() -> None:
    user_id = uuid4()
    mock_identity = MagicMock(spec=UserIdentity)
    mock_identity.user_id = user_id
    mock_identity.password_hash = "hashed_pw"

    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = mock_identity

    session = AsyncMock()
    session.execute.return_value = fake_result
    repo = SqlAlchemyTenantIdentityRepository(session)

    identity = await repo.get_standalone_identity(user_id)

    assert identity is not None
    assert identity.user_id == user_id
    assert identity.password_hash == "hashed_pw"


@pytest.mark.asyncio
async def test_get_identity_by_provider_returns_identity() -> None:
    idp_id = uuid4()
    mock_identity = MagicMock(spec=UserIdentity)
    mock_identity.identity_provider_id = idp_id
    mock_identity.provider_user_id = "user@test.com"

    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = mock_identity

    session = AsyncMock()
    session.execute.return_value = fake_result
    repo = SqlAlchemyTenantIdentityRepository(session)

    identity = await repo.get_identity_by_provider(idp_id, "user@test.com")

    assert identity is not None
    assert identity.identity_provider_id == idp_id
    assert identity.provider_user_id == "user@test.com"
