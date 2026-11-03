from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.composition.identity.wiring import (
    get_login_use_case,
    get_logout_use_case,
    get_refresh_tokens_use_case,
    get_register_use_case,
)
from app.modules.identity.application.functionality_usecases.login import Login
from app.modules.identity.application.functionality_usecases.logout import Logout
from app.modules.identity.application.functionality_usecases.refresh_tokens import (
    RefreshTokens,
)
from app.modules.identity.application.functionality_usecases.register import Register
from app.modules.identity.interface.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    UserProfileResponse,
)
from app.routers.security import require_trusted_origin

router = APIRouter(prefix="/auth", tags=["Identity"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in and issue access and refresh tokens",
    description=(
        "Authenticates credentials and returns a short-lived JWT access token "
        "and a rotating opaque refresh token in the response body. Use the "
        "access token as an Authorization: Bearer credential."
    ),
    dependencies=[Depends(require_trusted_origin)],
    responses={
        401: {"description": "The credentials are invalid or the account is inactive."},
        403: {"description": "The request origin is not allowed."},
    },
)
async def login(
    request: LoginRequest,
    use_case: Annotated[Login, Depends(get_login_use_case)],
) -> LoginResponse:
    result = await use_case.execute(request)
    return LoginResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        user=UserProfileResponse.model_validate(result.user),
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Rotate the refresh token",
    dependencies=[Depends(require_trusted_origin)],
)
async def refresh_tokens(
    request: RefreshRequest,
    use_case: Annotated[RefreshTokens, Depends(get_refresh_tokens_use_case)],
) -> RefreshResponse:
    result = await use_case.execute(request.refresh_token)
    return RefreshResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
    description="Revokes the refresh-token family supplied in the request body.",
    dependencies=[Depends(require_trusted_origin)],
)
async def logout(
    request: LogoutRequest,
    use_case: Annotated[Logout, Depends(get_logout_use_case)],
) -> Response:
    await use_case.execute(request.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
