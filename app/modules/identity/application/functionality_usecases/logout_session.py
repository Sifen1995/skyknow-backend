from app.modules.identity.domain.redis_repository import SessionRepository


class LogoutSession:
    def __init__(self, session_repository: SessionRepository) -> None:
        self._session_repository = session_repository

    async def execute(self, session_token: str) -> None:
        await self._session_repository.revoke(session_token)
