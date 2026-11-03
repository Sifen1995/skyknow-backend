import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from app.core.security import create_access_token
from app.modules.identity.application.errors import AuthenticationFailedError
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.identity_repository import IdentityRepository
from app.modules.identity.domain.refresh_token_repository import RefreshTokenRepository


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


class RefreshTokens:
    def __init__(
        self,
        identity_repository: IdentityRepository,
        refresh_token_repository: RefreshTokenRepository,
        access_token_ttl_seconds: int,
        refresh_token_ttl_seconds: int,
        jwt_secret_key: str,
        jwt_algorithm: str,
    ) -> None:
        self._identity_repository = identity_repository
        self._refresh_token_repository = refresh_token_repository
        self._access_token_ttl_seconds = access_token_ttl_seconds
        self._refresh_token_ttl_seconds = refresh_token_ttl_seconds
        self._jwt_secret_key = jwt_secret_key
        self._jwt_algorithm = jwt_algorithm

    async def execute(self, refresh_token: str) -> TokenPair:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        record = await self._refresh_token_repository.get_for_update(token_hash)
        now = datetime.now(UTC)
        if (
            record is None
            or record.revoked_at is not None
            or record.expires_at <= now
        ):
            raise AuthenticationFailedError("Refresh token is invalid or expired")

        user = await self._identity_repository.get_user_by_id(str(record.user_id))
        if user is None or user.status != UserStatus.ACTIVE:
            raise AuthenticationFailedError("Refresh token is invalid or expired")

        next_refresh_token = token_urlsafe(64)
        await self._refresh_token_repository.revoke(token_hash)
        await self._refresh_token_repository.create(
            token_hash=hashlib.sha256(next_refresh_token.encode()).hexdigest(),
            user_id=user.id,
            family_id=record.family_id,
            expires_at=now + timedelta(seconds=self._refresh_token_ttl_seconds),
        )
        return TokenPair(
            access_token=create_access_token(
                str(user.id),
                secret_key=self._jwt_secret_key,
                algorithm=self._jwt_algorithm,
                expires_seconds=self._access_token_ttl_seconds,
            ),
            refresh_token=next_refresh_token,
            expires_in=self._access_token_ttl_seconds,
        )