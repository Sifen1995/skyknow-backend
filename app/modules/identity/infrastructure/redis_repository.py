import hashlib
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis

from app.modules.identity.domain.redis_repository import SessionRecord


class RedisSessionRepository:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _key(session_token: str) -> str:
        digest = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
        return f"identity:session:{digest}"

    async def create(
        self,
        session_token: str,
        user_id: str,
        csrf_token: str,
        ttl_seconds: int,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("Session TTL must be positive")

        key = self._key(session_token)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.hset(
                key,
                mapping={"user_id": user_id, "csrf_token": csrf_token},
            )
            pipe.expire(key, ttl_seconds)
            await pipe.execute()

    async def get(self, session_token: str) -> SessionRecord | None:
        data = await cast(
            Awaitable[dict[str, str]],
            self._redis.hgetall(self._key(session_token)),
        )
        if not data:
            return None

        user_id = data.get("user_id")
        csrf_token = data.get("csrf_token")
        if not isinstance(user_id, str) or not isinstance(csrf_token, str):
            raise TypeError("Redis session record fields must be strings")

        return SessionRecord(user_id=user_id, csrf_token=csrf_token)

    async def revoke(self, session_token: str) -> None:
        await self._redis.delete(self._key(session_token))
