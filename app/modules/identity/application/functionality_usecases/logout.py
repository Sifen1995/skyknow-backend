import hashlib

from app.modules.identity.domain.refresh_token_repository import RefreshTokenRepository


class Logout:
    def __init__(self, refresh_token_repository: RefreshTokenRepository) -> None:
        self._refresh_token_repository = refresh_token_repository

    async def execute(self, refresh_token: str) -> None:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        record = await self._refresh_token_repository.get_for_update(token_hash)
        if record is not None:
            await self._refresh_token_repository.revoke_family(record.family_id)
