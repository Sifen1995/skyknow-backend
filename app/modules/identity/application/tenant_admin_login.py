import hashlib
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import uuid4

from app.core.security import create_access_token, verify_password
from app.modules.identity.application.dtos import (
    TenantLoginRequest,
    TenantLoginResult,
    TenantUserProfile,
)
from app.modules.identity.application.errors import (
    TenantAuthenticationFailedError,
    TenantUserDisabledError,
    TenantUserPendingError,
)
from app.modules.identity.application.validations.auth import (
    validate_tenant_login_request,
)
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.repository import (
    TenantIdentityRepository,
    TenantRefreshTokenRepository,
    TenantRoleRepository,
    TenantUserRepository,
)


class TenantLogin:
    """Authenticates both regular tenant users and tenant administrators.

    Determines role and admin status via role_id attached to the user,
    utilizing Redis-cached role lookups.
    """

    def __init__(
        self,
        user_repository: TenantUserRepository,
        identity_repository: TenantIdentityRepository,
        refresh_token_repository: TenantRefreshTokenRepository,
        access_token_ttl_seconds: int,
        refresh_token_ttl_seconds: int,
        jwt_secret_key: str,
        jwt_algorithm: str,
        role_repository: TenantRoleRepository | None = None,
    ) -> None:
        self._user_repo = user_repository
        self._identity_repo = identity_repository
        self._refresh_token_repo = refresh_token_repository
        self._access_token_ttl_seconds = access_token_ttl_seconds
        self._refresh_token_ttl_seconds = refresh_token_ttl_seconds
        self._jwt_secret_key = jwt_secret_key
        self._jwt_algorithm = jwt_algorithm
        self._role_repo = role_repository

    async def execute(
        self, request: TenantLoginRequest, *, subdomain: str
    ) -> TenantLoginResult:
        validated = validate_tenant_login_request(request)

        user = await self._user_repo.get_by_email(validated.email)
        if user is None:
            raise TenantAuthenticationFailedError("Invalid email or password")

        if user.status == UserStatus.DISABLED:
            raise TenantUserDisabledError("Your user account has been disabled")
        if user.status == UserStatus.PENDING:
            raise TenantUserPendingError("Your user account is pending approval")

        # Fetch standalone credentials (password hash)
        identity = await self._identity_repo.get_standalone_identity(user.id)
        if (
            identity is None
            or not identity.password_hash
            or not verify_password(validated.password, identity.password_hash)
        ):
            raise TenantAuthenticationFailedError("Invalid email or password")

        # Determine user role from role_id using Redis-cached roles
        role_name = "member"
        is_admin = False
        if user.role_id is not None and self._role_repo is not None:
            role_record = await self._role_repo.get_by_id(
                user.role_id, subdomain=subdomain
            )
            if role_record is not None:
                role_name = role_record.name
                is_admin = role_name == "admin"
        elif user.role is not None:
            role_name = (
                user.role.name.value
                if hasattr(user.role.name, "value")
                else str(user.role.name)
            )
            is_admin = role_name == "admin"

        now = datetime.now(UTC)
        await self._user_repo.update_last_login(user, now)

        # Invalidate prior active sessions for this user
        await self._refresh_token_repo.revoke_all_for_user(user.id)

        # Issue rotating refresh token at generation 1
        family_id = uuid4()
        raw_refresh_token = token_urlsafe(64)
        secret_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        expires_at = now + timedelta(seconds=self._refresh_token_ttl_seconds)

        await self._refresh_token_repo.store_refresh_token(
            family_id=family_id,
            user_id=user.id,
            secret_hash=secret_hash,
            expires_at=expires_at,
        )

        # Issue JWT access token with tenant context and role info
        access_token = create_access_token(
            str(user.id),
            secret_key=self._jwt_secret_key,
            algorithm=self._jwt_algorithm,
            expires_seconds=self._access_token_ttl_seconds,
            extra_claims={
                "tenant": subdomain,
                "role": role_name,
                "is_admin": is_admin,
                "email": user.email,
                "org_unit_id": str(user.organisation_unit_id),
            },
        )

        user_status_val = (
            user.status.value if hasattr(user.status, "value") else str(user.status)
        )
        user_profile = TenantUserProfile(
            id=user.id,
            name=user.name,
            email=user.email,
            role=role_name,
            organisation_unit_id=user.organisation_unit_id,
            status=user_status_val,
            is_admin=is_admin,
        )

        return TenantLoginResult(
            user=user_profile,
            access_token=access_token,
            refresh_token=raw_refresh_token,
            family_id=family_id,
            current_generation=1,
            expires_in=self._access_token_ttl_seconds,
        )


# Backwards compatibility alias
TenantAdminLogin = TenantLogin
