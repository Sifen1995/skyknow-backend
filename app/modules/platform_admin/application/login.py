import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID, uuid4

from app.core.security import create_access_token, verify_password
from app.modules.platform_admin.application.dtos import SuperUserRequest
from app.modules.platform_admin.application.errors import AuthenticationFailedError
from app.modules.platform_admin.application.validations.auth import (
    validate_login_request,
)
from app.modules.platform_admin.domain.models import PlatformAdmin
from app.modules.platform_admin.domain.platform_admin_repository import (
    PlatformAdminRefreshTokenRepository,
    PlatformAdminRepository,
)


@dataclass(frozen=True)
class LoginResult:
    admin: PlatformAdmin
    access_token: str
    refresh_token: str
    family_id: UUID
    current_generation: int
    expires_in: int


class Login:
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

    async def execute(self, request: SuperUserRequest) -> LoginResult:
        validated_request = validate_login_request(request)
        admin = await self._platform_admin_repository.get_platform_admin_by_email(
            validated_request.email
        )

        if (
            admin is None
            or not admin.password_hash
            or not verify_password(validated_request.password, admin.password_hash)
        ):
            raise AuthenticationFailedError("Invalid email or password")

        now = datetime.now(UTC)
        await self._platform_admin_repository.update_last_login(admin, now)

        # Invalidate any prior active session for this admin
        await self._refresh_token_repository.revoke_all_for_admin(admin.id)

        # Fresh login always initiates a new session at generation 1
        family_id = uuid4()
        raw_refresh_token = token_urlsafe(64)
        secret_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        expires_at = now + timedelta(seconds=self._refresh_token_ttl_seconds)

        await self._refresh_token_repository.store_refresh_token(
            family_id=family_id,
            platform_admin_id=admin.id,
            secret_hash=secret_hash,
            expires_at=expires_at,
        )

        access_token = create_access_token(
            str(admin.id),
            secret_key=self._jwt_secret_key,
            algorithm=self._jwt_algorithm,
            expires_seconds=self._access_token_ttl_seconds,
        )

        return LoginResult(
            admin=admin,
            access_token=access_token,
            refresh_token=raw_refresh_token,
            family_id=family_id,
            current_generation=1,
            expires_in=self._access_token_ttl_seconds,
        )
