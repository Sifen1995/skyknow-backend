from typing import cast

from redis.asyncio import Redis


def create_redis_client(url: str) -> Redis:
    return cast(
        Redis,
        Redis.from_url(url, decode_responses=True),
    )
