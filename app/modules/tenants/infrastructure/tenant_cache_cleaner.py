import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.modules.tenants.domain.repository import TenantCacheCleaner

logger = logging.getLogger(__name__)


class RedisTenantCacheCleaner(TenantCacheCleaner):
    """Cleans cached tenant data from Redis when a tenant is deleted."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def clear_tenant_cache(self, *, subdomain: str) -> None:
        pattern = f"tenant:{subdomain.lower()}:*"
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
                logger.info(
                    "Cleared %d Redis keys for tenant '%s'", len(keys), subdomain
                )
        except RedisError as exc:
            logger.warning(
                "Failed to clear Redis cache for tenant '%s': %s",
                subdomain,
                exc,
            )
