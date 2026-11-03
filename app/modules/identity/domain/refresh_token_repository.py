from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class RefreshTokenRecord:
    user_id: UUID
    family_id: UUID
    expires_at: datetime
    revoked_at: datetime | None


class RefreshTokenRepository(Protocol):
    async def create(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        family_id: UUID,
        expires_at: datetime,
    ) -> None: ...

    async def get_for_update(self, token_hash: str) -> RefreshTokenRecord | None: ...

    async def revoke(self, token_hash: str) -> None: ...

    async def revoke_family(self, family_id: UUID) -> None: ...
