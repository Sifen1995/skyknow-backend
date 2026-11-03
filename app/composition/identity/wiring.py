from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.composition.database import get_db
from app.composition.redis import get_redis
from app.config import settings
from app.modules.identity.application.functionality_usecases.authenticate_session import (
    AuthenticateSession,
)
from app.modules.identity.application.functionality_usecases.login import Login
from app.modules.identity.application.functionality_usecases.logout_session import (
    LogoutSession,
)
from app.modules.identity.application.functionality_usecases.register import Register
from app.modules.identity.infrastructure.redis_repository import (
    RedisSessionRepository,
)
from app.modules.identity.infrastructure.sqlalchemy_identity_repository import (
    SqlAlchemyIdentityRepository,
)


def get_login_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> Login:
    return Login(
        SqlAlchemyIdentityRepository(session),
        RedisSessionRepository(redis),
        settings.SESSION_TTL_SECONDS,
    )


def get_register_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Register:
    return Register(SqlAlchemyIdentityRepository(session))


def get_authenticate_session_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> AuthenticateSession:
    return AuthenticateSession(
        SqlAlchemyIdentityRepository(session),
        RedisSessionRepository(redis),
    )


def get_logout_session_use_case(
    redis: Annotated[Redis, Depends(get_redis)],
) -> LogoutSession:
    return LogoutSession(RedisSessionRepository(redis))
