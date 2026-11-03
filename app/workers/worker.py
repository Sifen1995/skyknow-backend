# app/workers/worker.py
import os
from collections.abc import Callable
from typing import Any, ClassVar

from arq.connections import RedisSettings


async def ping(ctx: dict[str, Any]) -> str:
    return "pong"


class WorkerSettings:
    functions: ClassVar[list[Callable[..., Any]]] = [ping]
    redis_settings = RedisSettings.from_dsn(
        os.getenv("REDIS_URL", "redis://redis:6379/0")
    )
