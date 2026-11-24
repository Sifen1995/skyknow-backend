import json
import logging
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain.models import Role
from app.modules.identity.domain.repository import RoleRecord

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600  # Cache roles for 1 hour


class CachedTenantRoleRepository:
    """Repository for tenant roles backed by Redis cache and PostgreSQL.

    Roles for each tenant schema are fetched from the database and cached
    in Redis under tenant-scoped keys:
      - `tenant:{subdomain}:roles` (JSON list of all roles)
      - `tenant:{subdomain}:role:{role_id}` (JSON object for fast direct lookup)
    """

    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._redis = redis

    async def get_by_id(self, role_id: UUID, *, subdomain: str) -> RoleRecord | None:
        """Fetch role by ID. Checks Redis cache first, falls back to DB."""
        cache_key = f"tenant:{subdomain}:role:{role_id}"
        try:
            cached = await self._redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return RoleRecord(
                    id=UUID(data["id"]),
                    name=data["name"],
                    scope=data["scope"],
                    description=data.get("description"),
                )
        except (RedisError, json.JSONDecodeError, KeyError) as exc:
            logger.warning(
                "Redis lookup failed for role %s in tenant %s: %s",
                role_id,
                subdomain,
                exc,
            )

        # Cache miss or Redis error: populate cache from DB
        roles = await self.get_all(subdomain=subdomain)
        for r in roles:
            if r.id == role_id:
                return r
        return None

    async def get_all(self, *, subdomain: str) -> list[RoleRecord]:
        """Fetch all roles for a tenant. Checks Redis, queries DB on miss, then populates Redis."""
        list_cache_key = f"tenant:{subdomain}:roles"
        try:
            cached_list = await self._redis.get(list_cache_key)
            if cached_list:
                items = json.loads(cached_list)
                return [
                    RoleRecord(
                        id=UUID(item["id"]),
                        name=item["name"],
                        scope=item["scope"],
                        description=item.get("description"),
                    )
                    for item in items
                ]
        except (RedisError, json.JSONDecodeError, KeyError) as exc:
            logger.warning(
                "Redis get_all failed for roles in tenant %s: %s",
                subdomain,
                exc,
            )

        # Query database in active tenant schema (search_path already set)
        result = await self._session.execute(select(Role))
        db_roles = result.scalars().all()

        records: list[RoleRecord] = []
        serialized_list = []
        for role in db_roles:
            role_name = (
                role.name.value if hasattr(role.name, "value") else str(role.name)
            )
            role_scope = (
                role.scope.value if hasattr(role.scope, "value") else str(role.scope)
            )
            record = RoleRecord(
                id=role.id,
                name=role_name,
                scope=role_scope,
                description=role.description,
            )
            records.append(record)
            payload = {
                "id": str(record.id),
                "name": record.name,
                "scope": record.scope,
                "description": record.description,
            }
            serialized_list.append(payload)

            # Cache individual role
            try:
                await self._redis.setex(
                    f"tenant:{subdomain}:role:{role.id}",
                    CACHE_TTL_SECONDS,
                    json.dumps(payload),
                )
            except RedisError as exc:
                logger.warning("Failed to cache role %s: %s", role.id, exc)

        try:
            await self._redis.setex(
                list_cache_key,
                CACHE_TTL_SECONDS,
                json.dumps(serialized_list),
            )
        except RedisError as exc:
            logger.warning(
                "Failed to cache role list for tenant %s: %s", subdomain, exc
            )

        return records
