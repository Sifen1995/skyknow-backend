from typing import Annotated

from fastapi import APIRouter, Depends

from app.composition.identity import (
    TenantContext,
    get_tenant_context,
    get_tenant_login_use_case,
    get_tenant_logout_use_case,
    get_tenant_refresh_use_case,
)
from app.modules.identity.application.dtos import (
    TenantLoginRequest,
    TenantLogoutRequest,
    TenantRefreshRequest,
)
from app.modules.identity.application.logout import TenantLogout
from app.modules.identity.application.refresh_token import TenantRefreshTokenUseCase
from app.modules.identity.application.tenant_admin_login import TenantLogin
from app.modules.identity.interface.schemas import (
    TenantLoginRequestBody,
    TenantLoginResponse,
    TenantLogoutRequestBody,
    TenantLogoutResponse,
    TenantRefreshRequestBody,
    TenantRefreshResponse,
    TenantUserProfileResponse,
)
from app.routers.security import require_trusted_origin

router = APIRouter(prefix="/identity", tags=["Identity"])


@router.post(
    "/login",
    response_model=TenantLoginResponse,
    summary="User Login",
    description=(
        "Authenticates tenant user or administrator credentials against the active tenant schema. "
        "User role and administrative privileges are resolved from the tenant's roles table via Redis cache. "
        "Tenant context is resolved via the 'X-Tenant-Subdomain' header or request host."
    ),
    dependencies=[Depends(require_trusted_origin)],
    responses={
        401: {"description": "Invalid credentials or unapproved account."},
        403: {"description": "User disabled or tenant inactive."},
        404: {"description": "Tenant not found."},
        422: {"description": "Validation error on request payload."},
    },
)
async def login(
    payload: TenantLoginRequestBody,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[TenantLogin, Depends(get_tenant_login_use_case)],
) -> TenantLoginResponse:
    request = TenantLoginRequest(email=str(payload.email), password=payload.password)
    result = await use_case.execute(request, subdomain=ctx.subdomain)
    return TenantLoginResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        family_id=result.family_id,
        current_generation=result.current_generation,
        token_type="bearer",
        expires_in=result.expires_in,
        user=TenantUserProfileResponse(
            id=result.user.id,
            name=result.user.name,
            email=result.user.email,
            role=result.user.role,
            organisation_unit_id=result.user.organisation_unit_id,
            status=result.user.status,
            is_admin=result.user.is_admin,
        ),
    )


@router.post(
    "/refresh",
    response_model=TenantRefreshResponse,
    summary="Rotate Refresh Token",
    description=(
        "Rotates a tenant user/admin refresh token family. Invalidates prior generation and detects "
        "theft if a revoked or stale generation is presented."
    ),
    dependencies=[Depends(require_trusted_origin)],
    responses={
        401: {"description": "Refresh token is invalid, expired, or compromised."},
        403: {"description": "Tenant inactive or user disabled."},
        404: {"description": "Tenant not found."},
        422: {"description": "Validation error on request payload."},
    },
)
async def refresh(
    payload: TenantRefreshRequestBody,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[
        TenantRefreshTokenUseCase, Depends(get_tenant_refresh_use_case)
    ],
) -> TenantRefreshResponse:
    request = TenantRefreshRequest(
        family_id=payload.family_id,
        count=payload.count,
        refresh_token=payload.refresh_token,
    )
    result = await use_case.execute(request, subdomain=ctx.subdomain)
    return TenantRefreshResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        family_id=result.family_id,
        current_generation=result.current_generation,
        token_type="bearer",
        expires_in=result.expires_in,
    )


@router.post(
    "/logout",
    response_model=TenantLogoutResponse,
    summary="User Logout",
    description="Invalidates the specified refresh token family for the user.",
    responses={
        404: {"description": "Tenant not found."},
        422: {"description": "Validation error on request payload."},
    },
)
async def logout(
    payload: TenantLogoutRequestBody,
    _ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    use_case: Annotated[TenantLogout, Depends(get_tenant_logout_use_case)],
) -> TenantLogoutResponse:
    request = TenantLogoutRequest(family_id=payload.family_id)
    await use_case.execute(request)
    return TenantLogoutResponse()
