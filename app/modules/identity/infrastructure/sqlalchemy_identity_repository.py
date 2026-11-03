from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain.models import OrgUnit, User


class SqlAlchemyIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_id(self, user_id: str | UUID) -> User | None:
        try:
            parsed_user_id = UUID(str(user_id))
        except (TypeError, ValueError):
            return None

        statement = select(User).where(User.id == parsed_user_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_org_unit(self, org_unit_id: UUID) -> OrgUnit | None:
        statement = select(OrgUnit).where(OrgUnit.id == org_unit_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        *,
        external_id: str,
        email: str,
        full_name: str,
        password_hash: str,
        org_unit_id: UUID,
    ) -> User | None:
        statement = (
            insert(User)
            .values(
                external_id=external_id,
                email=email,
                full_name=full_name,
                password_hash=password_hash,
                org_unit_id=org_unit_id,
            )
            .on_conflict_do_nothing()
            .returning(User)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def update_last_login(self, user: User, logged_in_at: datetime) -> None:
        user.last_login_at = logged_in_at
        await self._session.flush()
