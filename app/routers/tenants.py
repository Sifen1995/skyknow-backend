from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from app.composition.tenants import get_tenant_branding_use_case
from app.modules.tenants.application.errors import InvalidTenantInputError
from app.modules.tenants.application.get_tenant_branding import GetTenantBranding
from app.modules.tenants.interface.schemas import TenantBrandingResponse

router = APIRouter(prefix="/tenants", tags=["Tenants"])


def extract_tenant_identifier_from_request(
    request: Request,
    explicit_header: str | None = None,
) -> str:
    """Extract tenant subdomain or custom domain from request headers."""
    if explicit_header and explicit_header.strip():
        return explicit_header.strip().lower()

    header_val = (
        request.headers.get("x-tenant-subdomain")
        or request.headers.get("x-tenant")
        or ""
    ).strip()
    if header_val:
        return header_val.lower()

    raw_host = (
        request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    ).strip()
    if not raw_host:
        raise InvalidTenantInputError(
            "Missing tenant identification. Please provide the 'X-Tenant-Subdomain' header or access via a tenant host."
        )

    hostname = raw_host.split(":")[0].strip().lower()
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
        raise InvalidTenantInputError(
            "Cannot resolve tenant from root host. Please provide 'X-Tenant-Subdomain' header or use a tenant subdomain (e.g. cbe.localhost)."
        )

    parts = hostname.split(".")
    # e.g. "cbe.localhost"
    if len(parts) == 2 and parts[-1] == "localhost":
        return parts[0]

    # e.g. "cbe.skyknow.com"
    if len(parts) >= 3 and parts[0] not in ("www", "api", "app"):
        return parts[0]

    # Custom domain fallback (e.g. "portal.cbe.et")
    return hostname


@router.get(
    "/branding",
    response_model=TenantBrandingResponse,
    summary="Get tenant branding from header",
    description=(
        "Returns the public branding metadata (organization name, primary brand color, and logo) "
        "for a tenant resolved from request headers ('X-Tenant-Subdomain', 'X-Forwarded-Host', or 'Host')."
    ),
    responses={
        400: {"description": "Missing or unresolvable tenant header."},
        404: {"description": "Tenant was not found."},
    },
)
async def get_tenant_branding_from_header(
    request: Request,
    use_case: Annotated[GetTenantBranding, Depends(get_tenant_branding_use_case)],
    x_tenant_subdomain: Annotated[
        str | None,
        Header(
            alias="X-Tenant-Subdomain",
            description="Tenant subdomain (e.g. 'cbe').",
            examples=["cbe"],
        ),
    ] = None,
) -> TenantBrandingResponse:
    identifier = extract_tenant_identifier_from_request(
        request, explicit_header=x_tenant_subdomain
    )
    result = await use_case.execute(identifier)
    return TenantBrandingResponse.model_validate(result)


@router.get(
    "/branding/{identifier}",
    response_model=TenantBrandingResponse,
    summary="Get tenant branding by path parameter",
    description=(
        "Returns the public branding metadata (organization name, primary brand color, and logo) "
        "for a tenant resolved by subdomain or custom domain path parameter."
    ),
    responses={
        404: {"description": "Tenant was not found."},
    },
)
async def get_tenant_branding(
    identifier: str,
    use_case: Annotated[GetTenantBranding, Depends(get_tenant_branding_use_case)],
) -> TenantBrandingResponse:
    result = await use_case.execute(identifier)
    return TenantBrandingResponse.model_validate(result)
