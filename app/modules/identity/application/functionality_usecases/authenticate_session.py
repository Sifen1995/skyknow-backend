from dataclasses import dataclass

from app.modules.identity.domain.enums import UserStatus
from app.modules.identity.domain.identity_repository import IdentityRepository
from app.modules.identity.domain.redis_repository import SessionRepository


@dataclass(frozen=True)
class AuthenticatedSession:
    user_id: str
    csrf_token: str


class AuthenticateSession:
    def __init__(
        self,
        identity_repository: IdentityRepository,
        session_repository: SessionRepository,
    ) -> None:
        self._identity_repository = identity_repository
        self._session_repository = session_repository

    async def execute(self, session_token: str) -> AuthenticatedSession | None:
        session = await self._session_repository.get(session_token)
        if session is None:
            return None

        user = await self._identity_repository.get_user_by_id(session.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            await self._session_repository.revoke(session_token)
            return None

        return AuthenticatedSession(
            user_id=str(user.id),
            csrf_token=session.csrf_token,
        )
