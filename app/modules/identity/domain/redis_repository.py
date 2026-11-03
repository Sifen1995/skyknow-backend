from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SessionRecord:
    user_id: str
    csrf_token: str


class SessionRepository(Protocol):
    async def create(
        self,
        session_token: str,
        user_id: str,
        csrf_token: str,
        ttl_seconds: int,
    ) -> None: ...

    async def get(self, session_token: str) -> SessionRecord | None: ...

    async def revoke(self, session_token: str) -> None: ...
