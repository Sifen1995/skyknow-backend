from dataclasses import dataclass
from datetime import UTC, datetime
from secrets import token_urlsafe

from app.core.security import verify_password
from app.modules.identity.application.validation.auth import validate_login_request
from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.identity_repository import IdentityRepository
from app.modules.identity.domain.models import User
from app.modules.identity.domain.redis_repository import SessionRepository
from app.modules.identity.interface.schemas import LoginRequest


@dataclass(frozen=True)
class LoginResult:
    user: User
    session_token: str
    csrf_token: str


class Login:
    def __init__(
        self,
        identity_repository: IdentityRepository,
        session_repository: SessionRepository,
        session_ttl_seconds: int,
    ) -> None:
        self._identity_repository = identity_repository
        self._session_repository = session_repository
        self._session_ttl_seconds = session_ttl_seconds

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

        session_token = token_urlsafe(32)
        csrf_token = token_urlsafe(32)
        await self._session_repository.create(
            session_token=session_token,
            user_id=str(user.id),
            csrf_token=csrf_token,
            ttl_seconds=self._session_ttl_seconds,
        )

        return LoginResult(
            user=user,
            session_token=session_token,
            csrf_token=csrf_token,
        )
