from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.composition.database import get_db
from app.modules.knowledge.domain.models import Page, PageLanguage
from app.modules.knowledge.domain.page_repository import PageRepository


class GetAllPages:
    def __init__(self, page_repository: PageRepository) -> None:
        self._page_repository = page_repository

    async def execute(self) -> list[Page]:
        return await self._page_repository.get_all()


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


def get_all_pages_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GetAllPages:
    return GetAllPages(SqlAlchemyPageRepository(session))
