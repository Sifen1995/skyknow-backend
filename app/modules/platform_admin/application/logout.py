from app.modules.platform_admin.application.dtos import LogoutRequest
from app.modules.platform_admin.domain.platform_admin_repository import (
    PlatformAdminRefreshTokenRepository,
)


class Logout:
    def __init__(
        self,
        refresh_token_repository: PlatformAdminRefreshTokenRepository,
    ) -> None:
        self._refresh_token_repository = refresh_token_repository

    async def execute(self, request: LogoutRequest) -> None:
        await self._refresh_token_repository.revoke_refresh_token(request.family_id)
