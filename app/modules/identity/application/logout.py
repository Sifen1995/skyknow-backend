from app.modules.identity.application.dtos import TenantLogoutRequest
from app.modules.identity.domain.repository import TenantRefreshTokenRepository


class TenantLogout:
    def __init__(
        self,
        refresh_token_repository: TenantRefreshTokenRepository,
    ) -> None:
        self._refresh_token_repo = refresh_token_repository

    async def execute(self, request: TenantLogoutRequest) -> None:
        await self._refresh_token_repo.revoke_refresh_token(request.family_id)
