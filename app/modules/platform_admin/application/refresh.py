import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID

from app.core.security import create_access_token
from app.modules.platform_admin.application.dtos import RefreshRequest
from app.modules.platform_admin.application.errors import AuthenticationFailedError
from app.modules.platform_admin.domain.platform_admin_repository import (
    PlatformAdminRefreshTokenRepository,
    PlatformAdminRepository,
)


@dataclass(frozen=True)
class RefreshResult:
    access_token: str
    refresh_token: str
    family_id: UUID
    current_generation: int
    expires_in: int


class RefreshTokenUseCase:
    def __init__(
        self,
        platform_admin_repository: PlatformAdminRepository,
        refresh_token_repository: PlatformAdminRefreshTokenRepository,
        access_token_ttl_seconds: int,
        refresh_token_ttl_seconds: int,
        jwt_secret_key: str,
        jwt_algorithm: str,
    ) -> None:
        self._platform_admin_repository = platform_admin_repository
        self._refresh_token_repository = refresh_token_repository
        self._access_token_ttl_seconds = access_token_ttl_seconds
        self._refresh_token_ttl_seconds = refresh_token_ttl_seconds
        self._jwt_secret_key = jwt_secret_key
        self._jwt_algorithm = jwt_algorithm

    async def execute(self, request: RefreshRequest) -> RefreshResult:
        # 1. Fetch existing row for this family_id
        record = await self._refresh_token_repository.get_refresh_token(
            request.family_id
        )

        now = datetime.now(UTC)
        if record is None or record.revoked_at is not None or record.expires_at <= now:
            raise AuthenticationFailedError("Refresh token is invalid or expired")

        # 2. Check if the incoming token hash matches the stored secret_hash
        presented_hash = hashlib.sha256(request.refresh_token.encode()).hexdigest()
        if (
            record.current_generation != request.count
            or record.secret_hash != presented_hash
        ):
            # Token reuse/theft detection: immediately revoke the entire family
            await self._refresh_token_repository.revoke_refresh_token(request.family_id)
            raise AuthenticationFailedError(
                "Refresh token is invalid or has been compromised"
            )

        # 3. Verify the platform admin still exists
        admin = await self._platform_admin_repository.get_platform_admin_by_id(
            record.platform_admin_id
        )
        if admin is None:
            raise AuthenticationFailedError("Platform admin no longer exists")

        # 4. Generate new raw secret and compute hash
        new_raw_token = token_urlsafe(64)
        new_secret_hash = hashlib.sha256(new_raw_token.encode()).hexdigest()
        new_expires_at = now + timedelta(seconds=self._refresh_token_ttl_seconds)

        # 5. Update the same row for this family_id: increment count by +1 and update secret_hash
        new_generation = await self._refresh_token_repository.rotate_refresh_token(
            family_id=request.family_id,
            new_secret_hash=new_secret_hash,
            new_expires_at=new_expires_at,
        )

        # 6. Issue a new access token
        access_token = create_access_token(
            str(admin.id),
            secret_key=self._jwt_secret_key,
            algorithm=self._jwt_algorithm,
            expires_seconds=self._access_token_ttl_seconds,
        )

        return RefreshResult(
            access_token=access_token,
            refresh_token=new_raw_token,
            family_id=request.family_id,
            current_generation=new_generation,
            expires_in=self._access_token_ttl_seconds,
        )
