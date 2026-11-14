import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform_admin.domain.models import PlatformAdmin

logger = logging.getLogger(__name__)


class SqlAlchemyPlatformAdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Admin lookups
    # ------------------------------------------------------------------

    async def get_platform_admin_by_email(self, email: str) -> PlatformAdmin | None:
        """Return a platform admin by their email address."""
        result = await self._session.execute(
            select(PlatformAdmin).where(PlatformAdmin.email == email)
        )
        return result.scalar_one_or_none()

    async def create_platform_admin(
        self,
        *,
        name: str,
        email: str,
        password_hash: str,
        is_super_superuser: bool = False,
    ) -> PlatformAdmin | None:
        """Insert a platform admin unless the email already exists."""
        existing = await self.get_platform_admin_by_email(email)
        if existing is not None:
            return None

        admin = PlatformAdmin(
            name=name,
            email=email,
            password_hash=password_hash,
            is_super_superuser=is_super_superuser,
        )
        self._session.add(admin)
        await self._session.flush()
        return admin

    async def get_platform_admin_by_id(
        self, platform_admin_id: UUID
    ) -> PlatformAdmin | None:
        """Return a platform admin by their ID."""
        result = await self._session.execute(
            select(PlatformAdmin).where(PlatformAdmin.id == platform_admin_id)
        )
        return result.scalar_one_or_none()

    async def update_last_login(
        self, admin: PlatformAdmin, logged_in_at: datetime
    ) -> None:
        """Update last_login_at timestamp for a platform admin."""
        admin.last_login_at = logged_in_at
        await self._session.flush()
