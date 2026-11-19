from uuid import uuid4

import pytest

from app.modules.platform_admin.application.dtos import LogoutRequest
from app.modules.platform_admin.application.logout import Logout


class FakePlatformAdminRefreshTokenRepository:
    def __init__(self) -> None:
        self.revoked_families: list[object] = []

    async def store_refresh_token(self, **kwargs: object) -> None:
        pass

    async def get_refresh_token(self, family_id: object) -> None:
        return None

    async def get_refresh_token_by_admin_id(self, platform_admin_id: object) -> None:
        return None

    async def rotate_refresh_token(self, **kwargs: object) -> int:
        return 1

    async def revoke_refresh_token(self, family_id: object) -> None:
        self.revoked_families.append(family_id)

    async def revoke_all_for_admin(self, platform_admin_id: object) -> None:
        pass


@pytest.mark.asyncio
async def test_logout_revokes_token_family() -> None:
    fake_repo = FakePlatformAdminRefreshTokenRepository()
    use_case = Logout(refresh_token_repository=fake_repo)  # type: ignore[arg-type]

    family_id = uuid4()
    await use_case.execute(LogoutRequest(family_id=family_id))

    assert fake_repo.revoked_families == [family_id]
