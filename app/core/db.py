from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def build_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        create_async_engine(database_url, pool_pre_ping=True),
        expire_on_commit=False,
    )
