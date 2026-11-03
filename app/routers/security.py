from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.composition.identity.wiring import get_authenticate_access_token_use_case
from app.config import settings
from app.modules.identity.application.functionality_usecases.authenticate_access_token import (
    AuthenticateAccessToken,
    AuthenticatedUser,
)

bearer_scheme = HTTPBearer(auto_error=False)


async def require_trusted_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin not in settings.CORS_ALLOWED_ORIGINS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted request origin",
        )


async def require_authenticated_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    use_case: Annotated[
        AuthenticateAccessToken,
        Depends(get_authenticate_access_token_use_case),
    ],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    authenticated_user = await use_case.execute(credentials.credentials)
    if authenticated_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authenticated_user
