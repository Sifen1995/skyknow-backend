import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.composition.identity.wiring import get_authenticate_session_use_case
from app.config import settings
from app.modules.identity.application.functionality_usecases.authenticate_session import (
    AuthenticatedSession,
    AuthenticateSession,
)


async def require_trusted_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin not in settings.CORS_ALLOWED_ORIGINS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted request origin",
        )


async def require_authenticated_user(
    request: Request,
    use_case: Annotated[
        AuthenticateSession,
        Depends(get_authenticate_session_use_case),
    ],
    csrf_token: Annotated[
        str | None,
        Header(
            alias="X-CSRF-Token",
            description="Required for state-changing requests.",
        ),
    ] = None,
) -> AuthenticatedSession:
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    authenticated_session = await use_case.execute(session_token)
    if authenticated_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        )

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        await require_trusted_origin(request)
        if csrf_token is None or not secrets.compare_digest(
            csrf_token,
            authenticated_session.csrf_token,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed",
            )

    return authenticated_session
