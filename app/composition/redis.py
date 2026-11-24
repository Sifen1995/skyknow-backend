from redis.asyncio import Redis

from app.config import settings
from app.core.redis import create_redis_client

redis_client = create_redis_client(settings.REDIS_URL)


async def get_redis() -> Redis:
    return redis_client


async def close_redis() -> None:
    await redis_client.aclose()
