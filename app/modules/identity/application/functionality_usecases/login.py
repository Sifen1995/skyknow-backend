import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import uuid4

from app.core.security import create_access_token, verify_password
from app.modules.identity.application.validation.auth import validate_login_request
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.identity_repository import IdentityRepository
from app.modules.identity.domain.models import User
from app.modules.identity.domain.refresh_token_repository import RefreshTokenRepository
from app.modules.identity.interface.schemas import LoginRequest


@dataclass(frozen=True)
class LoginResult:
    user: User
    access_token: str
    refresh_token: str
    expires_in: int


class Login:
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

    async def execute(self, request: LoginRequest) -> LoginResult:
        validated_request = validate_login_request(request)
        user = await self._identity_repository.get_user_by_email(
            validated_request.email
        )

        if (
            user is None
            or user.status != UserStatus.ACTIVE
            or user.password_hash is None
            or not verify_password(validated_request.password, user.password_hash)
        ):
            from app.modules.identity.application.errors import (
                AuthenticationFailedError,
            )

            raise AuthenticationFailedError("Invalid email or password")

        await self._identity_repository.update_last_login(user, datetime.now(UTC))

        now = datetime.now(UTC)
        refresh_token = token_urlsafe(64)
        await self._refresh_token_repository.create(
            token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
            user_id=user.id,
            family_id=uuid4(),
            expires_at=now + timedelta(seconds=self._refresh_token_ttl_seconds),
        )
        access_token = create_access_token(
            str(user.id),
            secret_key=self._jwt_secret_key,
            algorithm=self._jwt_algorithm,
            expires_seconds=self._access_token_ttl_seconds,
        )

        return LoginResult(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._access_token_ttl_seconds,
        )
