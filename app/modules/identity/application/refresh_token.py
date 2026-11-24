import hashlib
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from app.core.security import create_access_token
from app.modules.identity.application.dtos import (
    TenantRefreshRequest,
    TenantRefreshResult,
)
from app.modules.identity.application.errors import (
    TenantAuthenticationFailedError,
    TenantRefreshTokenInvalidError,
    TenantUserDisabledError,
)
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.repository import (
    TenantRefreshTokenRepository,
    TenantUserRepository,
)


class TenantRefreshTokenUseCase:
    def __init__(
        self,
        user_repository: TenantUserRepository,
        refresh_token_repository: TenantRefreshTokenRepository,
        access_token_ttl_seconds: int,
        refresh_token_ttl_seconds: int,
        jwt_secret_key: str,
        jwt_algorithm: str,
    ) -> None:
        self._user_repo = user_repository
        self._refresh_token_repo = refresh_token_repository
        self._access_token_ttl_seconds = access_token_ttl_seconds
        self._refresh_token_ttl_seconds = refresh_token_ttl_seconds
        self._jwt_secret_key = jwt_secret_key
        self._jwt_algorithm = jwt_algorithm

    async def execute(
        self, request: TenantRefreshRequest, *, subdomain: str
    ) -> TenantRefreshResult:
        record = await self._refresh_token_repo.get_refresh_token(request.family_id)
        now = datetime.now(UTC)

        if record is None or record.revoked_at is not None or record.expires_at <= now:
            raise TenantRefreshTokenInvalidError("Refresh token is invalid or expired")

        presented_hash = hashlib.sha256(request.refresh_token.encode()).hexdigest()
        if (
            record.current_generation != request.count
            or record.secret_hash != presented_hash
        ):
            # Token reuse/theft detection: immediately revoke the entire family
            await self._refresh_token_repo.revoke_refresh_token(request.family_id)
            raise TenantRefreshTokenInvalidError(
                "Refresh token is invalid or has been compromised"
            )

        user = await self._user_repo.get_by_id(record.user_id)
        if user is None:
            raise TenantAuthenticationFailedError("User no longer exists")
        if user.status != UserStatus.ACTIVE:
            raise TenantUserDisabledError("User account is not active")

        # Generate new secret and rotate
        new_raw_token = token_urlsafe(64)
        new_secret_hash = hashlib.sha256(new_raw_token.encode()).hexdigest()
        new_expires_at = now + timedelta(seconds=self._refresh_token_ttl_seconds)

        new_generation = await self._refresh_token_repo.rotate_refresh_token(
            family_id=request.family_id,
            new_secret_hash=new_secret_hash,
            new_expires_at=new_expires_at,
        )

        role_name = str(user.role.name) if user.role else "user"
        access_token = create_access_token(
            str(user.id),
            secret_key=self._jwt_secret_key,
            algorithm=self._jwt_algorithm,
            expires_seconds=self._access_token_ttl_seconds,
            extra_claims={
                "tenant": subdomain,
                "role": role_name,
                "email": user.email,
                "org_unit_id": str(user.organisation_unit_id),
            },
        )

        return TenantRefreshResult(
            access_token=access_token,
            refresh_token=new_raw_token,
            family_id=request.family_id,
            current_generation=new_generation,
            expires_in=self._access_token_ttl_seconds,
        )
