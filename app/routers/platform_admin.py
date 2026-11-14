from typing import Annotated

from fastapi import APIRouter, Depends

from app.composition.platform_admin import (
    get_platform_admin_login_use_case,
    get_platform_admin_refresh_use_case,
)
from app.modules.platform_admin.application.login import Login
from app.modules.platform_admin.application.refresh import RefreshTokenUseCase
from app.modules.platform_admin.interface.schemas import (
    RefreshRequest,
    RefreshResponse,
    SuperUserProfileResponse,
    SuperUserRequest,
    SuperUserResponse,
)
from app.routers.security import require_trusted_origin

router = APIRouter(prefix="/platform-admin", tags=["Platform Admin"])


@router.post(
    "/login",
    response_model=SuperUserResponse,
    summary="Platform admin login",
    description=(
        "Authenticates platform administrator credentials and returns an access token, "
        "rotating refresh token, and administrator profile."
    ),
    dependencies=[Depends(require_trusted_origin)],
    responses={
        401: {"description": "Invalid email or password."},
        403: {"description": "Untrusted request origin."},
        422: {"description": "Validation error on request body."},
    },
)
async def login(
    request: SuperUserRequest,
    use_case: Annotated[Login, Depends(get_platform_admin_login_use_case)],
) -> SuperUserResponse:
    result = await use_case.execute(request)
    return SuperUserResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        family_id=result.family_id,
        current_generation=result.current_generation,
        token_type="bearer",
        expires_in=result.expires_in,
        admin=SuperUserProfileResponse.model_validate(result.admin),
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Rotate platform admin refresh token",
    description=(
        "Validates the incoming family_id, generation count, and refresh token secret. "
        "Atomically increments the count, stores the new secret hash in the same row, "
        "and returns a fresh access token and rotated refresh token."
    ),
    dependencies=[Depends(require_trusted_origin)],
    responses={
        401: {"description": "Refresh token is invalid, expired, or compromised."},
        403: {"description": "Untrusted request origin."},
        422: {"description": "Validation error on request body."},
    },
)
async def refresh_token(
    request: RefreshRequest,
    use_case: Annotated[
        RefreshTokenUseCase, Depends(get_platform_admin_refresh_use_case)
    ],
) -> RefreshResponse:
    result = await use_case.execute(request)
    return RefreshResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        family_id=result.family_id,
        current_generation=result.current_generation,
        token_type="bearer",
        expires_in=result.expires_in,
    )
