import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.identity.domain.enums import RoleScope, SystemRole
from app.modules.identity.domain.models import Role
from app.modules.identity.infrastructure.tenant_role_sql import (
    CachedTenantRoleRepository,
)


@pytest.mark.asyncio
async def test_get_by_id_returns_cached_role_from_redis() -> None:
    role_id = uuid4()
    subdomain = "acme"
    cached_payload = json.dumps(
        {
            "id": str(role_id),
            "name": "admin",
            "scope": "company",
            "description": "Full Admin",
        }
    )

    redis = AsyncMock()
    redis.get.return_value = cached_payload

    session = AsyncMock()
    repo = CachedTenantRoleRepository(session, redis)

    role = await repo.get_by_id(role_id, subdomain=subdomain)

    assert role is not None
    assert role.id == role_id
    assert role.name == "admin"
    assert role.scope == "company"
    redis.get.assert_awaited_once_with(f"tenant:{subdomain}:role:{role_id}")
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_by_id_falls_back_to_db_and_populates_redis_on_miss() -> None:
    role_id = uuid4()
    subdomain = "acme"

    redis = AsyncMock()
    redis.get.return_value = None  # Cache miss

    db_role = MagicMock(spec=Role)
    db_role.id = role_id
    db_role.name = SystemRole.ADMIN
    db_role.scope = RoleScope.COMPANY
    db_role.description = "Administrator"

    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = [db_role]

    session = AsyncMock()
    session.execute.return_value = fake_result

    repo = CachedTenantRoleRepository(session, redis)

    role = await repo.get_by_id(role_id, subdomain=subdomain)

    assert role is not None
    assert role.id == role_id
    assert role.name == "admin"
    session.execute.assert_awaited_once()
    assert redis.setex.await_count >= 1


@pytest.mark.asyncio
async def test_get_all_returns_cached_list_from_redis() -> None:
    subdomain = "acme"
    role_id = uuid4()
    cached_list = json.dumps(
        [
            {
                "id": str(role_id),
                "name": "author",
                "scope": "own_unit",
                "description": "Author role",
            }
        ]
    )

    redis = AsyncMock()
    redis.get.return_value = cached_list

    session = AsyncMock()
    repo = CachedTenantRoleRepository(session, redis)

    roles = await repo.get_all(subdomain=subdomain)

    assert len(roles) == 1
    assert roles[0].id == role_id
    assert roles[0].name == "author"
    session.execute.assert_not_called()
