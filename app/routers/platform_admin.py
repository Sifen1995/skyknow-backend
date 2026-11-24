import dataclasses
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.composition.platform_admin import (
    get_platform_admin_login_use_case,
    get_platform_admin_logout_use_case,
    get_platform_admin_refresh_use_case,
)
from app.composition.tenants import (
    get_delete_tenant_use_case,
    get_provision_tenant_use_case,
    get_upload_tenant_logo_use_case,
)
from app.modules.platform_admin.application.login import Login
from app.modules.platform_admin.application.logout import Logout
from app.modules.platform_admin.application.refresh import RefreshTokenUseCase
from app.modules.platform_admin.interface.schemas import (
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    SuperUserProfileResponse,
    SuperUserRequest,
    SuperUserResponse,
)
from app.modules.tenants.application.delete_tenant import DeleteTenant
from app.modules.tenants.application.dtos import ProvisionTenantInput
from app.modules.tenants.application.provision_tenant import ProvisionTenant
from app.modules.tenants.application.upload_tenant_logo import UploadTenantLogo
from app.modules.tenants.interface.schemas import (
    DeleteTenantResponse,
    ProvisionTenantForm,
    ProvisionTenantResponse,
    UploadTenantLogoResponse,
)
from app.routers.security import (
    require_authenticated_platform_admin,
    require_trusted_origin,
)

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


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Platform admin logout",
    description="Revokes the platform admin refresh token family.",
    dependencies=[Depends(require_trusted_origin)],
    responses={
        204: {"description": "Successfully logged out."},
        403: {"description": "Untrusted request origin."},
        422: {"description": "Validation error on request body."},
    },
)
async def logout(
    request: LogoutRequest,
    use_case: Annotated[Logout, Depends(get_platform_admin_logout_use_case)],
) -> Response:
    await use_case.execute(request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/tenants",
    status_code=status.HTTP_201_CREATED,
    response_model=ProvisionTenantResponse,
    summary="Provision a new tenant",
    description=(
        "Registers a new tenant, dynamically creates its isolated PostgreSQL schema, "
        "executes the tenant schema DDL, seeds initial roles and organization structure, "
        "and creates the initial tenant administrator."
    ),
    dependencies=[
        Depends(require_trusted_origin),
        Depends(require_authenticated_platform_admin),
    ],
    responses={
        201: {"description": "Tenant provisioned successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Untrusted request origin."},
        409: {"description": "Subdomain or custom domain already exists."},
        422: {"description": "Validation error on request body."},
        500: {"description": "Tenant provisioning failed."},
    },
)
async def provision_tenant(
    form: Annotated[ProvisionTenantForm, Depends()],
    provision_use_case: Annotated[
        ProvisionTenant, Depends(get_provision_tenant_use_case)
    ],
    upload_logo_use_case: Annotated[
        UploadTenantLogo, Depends(get_upload_tenant_logo_use_case)
    ],
) -> ProvisionTenantResponse:
    result = await provision_use_case.execute(
        ProvisionTenantInput(
            name=form.name,
            subdomain=form.subdomain,
            admin_email=form.admin_email,
            admin_name=form.admin_name,
            temporary_password=form.temporary_password,
            hosting_mode=form.hosting_mode,
            custom_domain=form.custom_domain,
            primary_color=form.primary_color,
            logo_url=None,
        )
    )

    # If logo file is uploaded directly in Swagger/form, save and update logo_url
    if form.logo is not None and form.logo.filename:
        logo_content = await form.logo.read()
        if logo_content:
            logo_url = await upload_logo_use_case.execute(
                subdomain=form.subdomain,
                file_bytes=logo_content,
                content_type=form.logo.content_type,
                filename=form.logo.filename,
            )
            result = dataclasses.replace(result, logo_url=logo_url)

    return ProvisionTenantResponse.model_validate(result)


@router.post(
    "/tenants/{subdomain}/logo",
    response_model=UploadTenantLogoResponse,
    summary="Upload tenant brand logo",
    description=(
        "Uploads a brand logo file (PNG, JPEG, SVG, WebP, max 2MB) for the specified tenant. "
        "Saves the asset to the server's asset directory and stores the public URL in the database."
    ),
    dependencies=[
        Depends(require_trusted_origin),
        Depends(require_authenticated_platform_admin),
    ],
    responses={
        200: {"description": "Logo uploaded successfully."},
        400: {"description": "Invalid file format or file size."},
        401: {"description": "Authentication required."},
        403: {"description": "Untrusted request origin."},
        404: {"description": "Tenant was not found."},
        422: {"description": "Invalid file upload or tenant identifier."},
    },
)
async def upload_tenant_logo(
    subdomain: str,
    file: Annotated[UploadFile, File(...)],
    use_case: Annotated[UploadTenantLogo, Depends(get_upload_tenant_logo_use_case)],
) -> UploadTenantLogoResponse:
    content = await file.read()
    logo_url = await use_case.execute(
        subdomain=subdomain,
        file_bytes=content,
        content_type=file.content_type,
        filename=file.filename,
    )
    return UploadTenantLogoResponse(
        subdomain=subdomain,
        logo_url=logo_url,
    )


@router.delete(
    "/tenants/{subdomain}",
    response_model=DeleteTenantResponse,
    summary="Delete a tenant",
    description=(
        "Completely deletes a tenant from the database (including dropping its dedicated schema "
        "and all associated tables/objects), removes its uploaded brand logo and assets from disk "
        "(served by Nginx), and invalidates all cached tenant entries in Redis."
    ),
    dependencies=[
        Depends(require_trusted_origin),
        Depends(require_authenticated_platform_admin),
    ],
    responses={
        200: {"description": "Tenant and assets deleted successfully."},
        401: {"description": "Authentication required."},
        403: {"description": "Untrusted request origin."},
        404: {"description": "Tenant was not found."},
    },
)
async def delete_tenant(
    subdomain: str,
    use_case: Annotated[DeleteTenant, Depends(get_delete_tenant_use_case)],
) -> DeleteTenantResponse:
    await use_case.execute(subdomain=subdomain)
    return DeleteTenantResponse(
        subdomain=subdomain,
        message=f"Tenant '{subdomain}' and all its assets have been successfully deleted.",
    )
