from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.composition.database import get_db
from app.config import settings
from app.modules.identity.application.functionality_usecases.authenticate_access_token import (
    AuthenticateAccessToken,
)
from app.modules.identity.application.functionality_usecases.login import Login
from app.modules.identity.application.functionality_usecases.logout import Logout
from app.modules.identity.application.functionality_usecases.refresh_tokens import (
    RefreshTokens,
)
from app.modules.identity.application.functionality_usecases.register import Register
from app.modules.identity.infrastructure.sqlalchemy_identity_repository import (
    SqlAlchemyIdentityRepository,
)
from app.modules.identity.infrastructure.sqlalchemy_refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)


def get_login_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Login:
    return Login(
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyRefreshTokenRepository(session),
        settings.ACCESS_TOKEN_TTL_SECONDS,
        settings.REFRESH_TOKEN_TTL_SECONDS,
        settings.SECRET_KEY.get_secret_value(),
        settings.ALGORITHM,
    )


def get_register_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Register:
    return Register(SqlAlchemyIdentityRepository(session))


def get_authenticate_access_token_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthenticateAccessToken:
    return AuthenticateAccessToken(
        SqlAlchemyIdentityRepository(session),
        settings.SECRET_KEY.get_secret_value(),
        settings.ALGORITHM,
    )


def get_refresh_tokens_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RefreshTokens:
    return RefreshTokens(
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyRefreshTokenRepository(session),
        settings.ACCESS_TOKEN_TTL_SECONDS,
        settings.REFRESH_TOKEN_TTL_SECONDS,
        settings.SECRET_KEY.get_secret_value(),
        settings.ALGORITHM,
    )


def get_logout_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Logout:
    return Logout(SqlAlchemyRefreshTokenRepository(session))
