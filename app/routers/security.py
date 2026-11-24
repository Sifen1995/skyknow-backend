from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.core.security import decode_access_token, verify_trusted_origin

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str


@dataclass(frozen=True)
class AuthenticatedPlatformAdmin:
    admin_id: str


async def require_trusted_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not verify_trusted_origin(origin, settings.CORS_ALLOWED_ORIGINS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted request origin",
        )


async def require_authenticated_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(
            credentials.credentials,
            secret_key=settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.ALGORITHM,
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if payload.get("token_use") != "access" or not isinstance(user_id, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(user_id=user_id)


async def require_authenticated_platform_admin(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedPlatformAdmin:
    user = await require_authenticated_user(credentials)
    return AuthenticatedPlatformAdmin(admin_id=user.user_id)
