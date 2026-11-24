from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.composition.database import get_db
from app.config import settings
from app.modules.platform_admin.application.login import Login
from app.modules.platform_admin.application.logout import Logout
from app.modules.platform_admin.application.refresh import RefreshTokenUseCase
from app.modules.platform_admin.infrastructure.platform_admin_refresh_sql import (
    SqlAlchemyPlatformAdminRefreshRepository,
)
from app.modules.platform_admin.infrastructure.platform_admin_sql import (
    SqlAlchemyPlatformAdminRepository,
)


def get_platform_admin_login_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Login:
    return Login(
        platform_admin_repository=SqlAlchemyPlatformAdminRepository(session),
        refresh_token_repository=SqlAlchemyPlatformAdminRefreshRepository(session),
        access_token_ttl_seconds=settings.ACCESS_TOKEN_TTL_SECONDS,
        refresh_token_ttl_seconds=settings.REFRESH_TOKEN_TTL_SECONDS,
        jwt_secret_key=settings.SECRET_KEY.get_secret_value(),
        jwt_algorithm=settings.ALGORITHM,
    )


def get_platform_admin_refresh_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(
        platform_admin_repository=SqlAlchemyPlatformAdminRepository(session),
        refresh_token_repository=SqlAlchemyPlatformAdminRefreshRepository(session),
        access_token_ttl_seconds=settings.ACCESS_TOKEN_TTL_SECONDS,
        refresh_token_ttl_seconds=settings.REFRESH_TOKEN_TTL_SECONDS,
        jwt_secret_key=settings.SECRET_KEY.get_secret_value(),
        jwt_algorithm=settings.ALGORITHM,
    )


def get_platform_admin_logout_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Logout:
    return Logout(
        refresh_token_repository=SqlAlchemyPlatformAdminRefreshRepository(session),
    )
