"""Alembic environment: how migrations connect to the database and run.

The database address comes from the DATABASE_URL environment variable,
the same one the app uses, so there is one place to configure it.
"""

# migrations/env.py
import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# --- ADD THIS TO LET PYTHON FIND YOUR APP MODULES ---
# (Assumes your config.py is inside an `app` folder at your project root)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings  # Import your Pydantic settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # Change to Base.metadata when you have models


def get_url() -> str:
    # --- PULL DIRECTLY FROM YOUR PYDANTIC SETTINGS ---
    url = settings.DATABASE_URL
    # Ensure it uses the async driver required by Alembic's async template
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """Print the SQL instead of running it: alembic upgrade head --sql"""
    context.configure(
        url=get_url(), target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_url()
    engine = async_engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
