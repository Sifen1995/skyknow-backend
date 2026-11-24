from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.composition.database import get_db
from app.composition.redis import get_redis
from app.config import settings
from app.modules.identity.application.errors import (
    TenantInactiveError,
    TenantNotFoundError,
)
from app.modules.identity.application.logout import TenantLogout
from app.modules.identity.application.refresh_token import TenantRefreshTokenUseCase
from app.modules.identity.application.tenant_admin_login import TenantLogin
from app.modules.identity.infrastructure.tenant_refresh_sql import (
    SqlAlchemyTenantRefreshTokenRepository,
)
from app.modules.identity.infrastructure.tenant_role_sql import (
    CachedTenantRoleRepository,
)
from app.modules.identity.infrastructure.tenant_user_sql import (
    SqlAlchemyTenantIdentityRepository,
    SqlAlchemyTenantUserRepository,
)
from app.modules.tenants.domain.enums import TenantStatus
from app.modules.tenants.infrastructure.schema_provisioner import generate_schema_name
from app.modules.tenants.infrastructure.tenant_sql import SqlAlchemyTenantRepository


@dataclass(frozen=True)
class TenantContext:
    subdomain: str
    schema_name: str
    session: AsyncSession


def extract_tenant_identifier(
    request: Request,
    explicit_header: str | None = None,
) -> str:
    """Extract tenant subdomain or custom domain from request headers or host."""
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
        raise TenantNotFoundError(
            "Missing tenant identification. Please provide the 'X-Tenant-Subdomain' header or access via a tenant host."
        )

    hostname = raw_host.split(":")[0].strip().lower()
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
        raise TenantNotFoundError(
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


async def get_tenant_context(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_subdomain: Annotated[
        str | None,
        Header(
            alias="X-Tenant-Subdomain",
            description="Tenant subdomain (e.g. 'cbe', 'ethiotelecom') or custom domain",
            examples=["cbe"],
        ),
    ] = None,
) -> TenantContext:
    """Resolve tenant from request, verify existence and active status, and set search_path."""
    identifier = extract_tenant_identifier(request, x_tenant_subdomain)
    tenant_repo = SqlAlchemyTenantRepository(session)
    tenant = await tenant_repo.get_by_subdomain_or_custom_domain(identifier)
    if tenant is None:
        raise TenantNotFoundError(f"Tenant '{identifier}' not found")
    if tenant.status != TenantStatus.ACTIVE:
        raise TenantInactiveError(f"Tenant '{tenant.subdomain}' is not active")

    schema_name = generate_schema_name(tenant.subdomain)
    await session.execute(text(f'SET search_path TO "{schema_name}", public'))

    return TenantContext(
        subdomain=tenant.subdomain,
        schema_name=schema_name,
        session=session,
    )


def get_tenant_login_use_case(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> TenantLogin:
    role_repo = CachedTenantRoleRepository(ctx.session, redis)
    return TenantLogin(
        user_repository=SqlAlchemyTenantUserRepository(ctx.session),
        identity_repository=SqlAlchemyTenantIdentityRepository(ctx.session),
        refresh_token_repository=SqlAlchemyTenantRefreshTokenRepository(ctx.session),
        access_token_ttl_seconds=settings.ACCESS_TOKEN_TTL_SECONDS,
        refresh_token_ttl_seconds=settings.REFRESH_TOKEN_TTL_SECONDS,
        jwt_secret_key=settings.SECRET_KEY.get_secret_value(),
        jwt_algorithm=settings.ALGORITHM,
        role_repository=role_repo,
    )


# Backwards compatibility alias
get_tenant_admin_login_use_case = get_tenant_login_use_case


def get_tenant_refresh_use_case(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantRefreshTokenUseCase:
    return TenantRefreshTokenUseCase(
        user_repository=SqlAlchemyTenantUserRepository(ctx.session),
        refresh_token_repository=SqlAlchemyTenantRefreshTokenRepository(ctx.session),
        access_token_ttl_seconds=settings.ACCESS_TOKEN_TTL_SECONDS,
        refresh_token_ttl_seconds=settings.REFRESH_TOKEN_TTL_SECONDS,
        jwt_secret_key=settings.SECRET_KEY.get_secret_value(),
        jwt_algorithm=settings.ALGORITHM,
    )


def get_tenant_logout_use_case(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantLogout:
    return TenantLogout(
        refresh_token_repository=SqlAlchemyTenantRefreshTokenRepository(ctx.session),
    )
