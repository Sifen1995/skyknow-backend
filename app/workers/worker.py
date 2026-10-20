# app/workers/worker.py
import os
from arq.connections import RedisSettings

async def ping(ctx):
    return "pong"

class WorkerSettings:
    functions = [ping]   # arq refuses to start with nothing registered
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://redis:6379/0"))