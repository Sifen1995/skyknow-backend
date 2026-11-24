from datetime import datetime
from uuid import UUID

from sqlalchemy import cast, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.types import String

from app.modules.identity.domain.enums import IdPType
from app.modules.identity.domain.models import IdentityProvider, User, UserIdentity


class SqlAlchemyTenantUserRepository:
    """SQLAlchemy implementation of TenantUserRepository.

    Executes against the active tenant schema set via PostgreSQL search_path.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).options(joinedload(User.role)).where(User.email == email)
        )
        return result.unique().scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(
            select(User).options(joinedload(User.role)).where(User.id == user_id)
        )
        return result.unique().scalar_one_or_none()

    async def update_last_login(self, user: User, timestamp: datetime) -> None:
        """In-place HOT update: only update unindexed 'last_login_at' column."""
        await self._session.execute(
            update(User).where(User.id == user.id).values(last_login_at=timestamp)
        )
        user.last_login_at = timestamp
        await self._session.flush()


class SqlAlchemyTenantIdentityRepository:
    """SQLAlchemy implementation of TenantIdentityRepository.

    Executes against the active tenant schema set via PostgreSQL search_path.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_standalone_identity(self, user_id: UUID) -> UserIdentity | None:
        result = await self._session.execute(
            select(UserIdentity)
            .join(
                IdentityProvider,
                UserIdentity.identity_provider_id == IdentityProvider.id,
            )
            .where(
                UserIdentity.user_id == user_id,
                cast(IdentityProvider.type, String) == IdPType.STANDALONE.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_identity_by_provider(
        self, identity_provider_id: UUID, provider_user_id: str
    ) -> UserIdentity | None:
        result = await self._session.execute(
            select(UserIdentity).where(
                UserIdentity.identity_provider_id == identity_provider_id,
                UserIdentity.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()
