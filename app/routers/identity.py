from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.composition.identity.wiring import (
    get_login_use_case,
    get_logout_session_use_case,
    get_register_use_case,
)
from app.config import settings
from app.modules.identity.application.functionality_usecases.authenticate_session import (
    AuthenticatedSession,
)
from app.modules.identity.application.functionality_usecases.login import Login
from app.modules.identity.application.functionality_usecases.logout_session import (
    LogoutSession,
)
from app.modules.identity.application.functionality_usecases.register import Register
from app.modules.identity.interface.schemas import (
    CsrfResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    UserProfileResponse,
)
from app.routers.security import require_authenticated_user, require_trusted_origin

router = APIRouter(prefix="/auth", tags=["Identity"])
CurrentSession = Annotated[
    AuthenticatedSession,
    Depends(require_authenticated_user),
]


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in and create a session",
    description=(
        "Authenticates the supplied credentials and creates a server-side "
        "session. The opaque session token is set in an HttpOnly cookie; it "
        "is not returned in the JSON body. The response body contains the "
        "CSRF token needed for subsequent state-changing requests. Requests "
        "must come from an origin listed in CORS_ALLOWED_ORIGINS."
    ),
    dependencies=[Depends(require_trusted_origin)],
    responses={
        200: {
            "description": (
                "Login succeeded. Sets the opaque session token in an HttpOnly cookie."
            ),
            "headers": {
                "Set-Cookie": {
                    "description": (
                        "Contains the opaque session cookie. The browser "
                        "stores it; JavaScript cannot read it."
                    ),
                    "schema": {"type": "string"},
                }
            },
        },
        401: {"description": "The credentials are invalid or the account is inactive."},
        403: {"description": "The request origin is not allowed."},
    },
)
async def login(
    request: LoginRequest,
    response: Response,
    use_case: Annotated[Login, Depends(get_login_use_case)],
) -> LoginResponse:
    result = await use_case.execute(request)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=result.session_token,
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )
    return LoginResponse(
        csrf_token=result.csrf_token,
        user=UserProfileResponse.model_validate(result.user),
    )


@router.get(
    "/csrf",
    response_model=CsrfResponse,
    summary="Get the current session's CSRF token",
    description=(
        "Returns the CSRF token associated with the authenticated session. "
        "The browser must send the session cookie."
    ),
    dependencies=[Depends(require_authenticated_user)],
)
async def get_csrf_token(session: CurrentSession) -> CsrfResponse:
    return CsrfResponse(csrf_token=session.csrf_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
    description=(
        "Revokes the current server-side session and clears its cookie. "
        "Requires the session cookie and the X-CSRF-Token header."
    ),
    dependencies=[Depends(require_authenticated_user)],
)
async def logout(
    request: Request,
    response: Response,
    use_case: Annotated[LogoutSession, Depends(get_logout_session_use_case)],
) -> Response:
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    await use_case.execute(session_token)
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )
    return response


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
async def register(
    request: RegisterRequest,
    use_case: Annotated[Register, Depends(get_register_use_case)],
) -> RegisterResponse:
    return await use_case.execute(request)
