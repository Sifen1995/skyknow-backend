from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.knowledge.domain.models import Page, PageLanguage


class SqlAlchemyPageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> list[Page]:
        statement = (
            select(Page)
            .options(
                selectinload(Page.audiences),
                selectinload(Page.languages).selectinload(PageLanguage.versions),
            )
            .order_by(Page.created_at.desc(), Page.id)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().unique().all())
