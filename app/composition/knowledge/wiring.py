from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.composition.database import get_db
from app.modules.knowledge.application.get_visible_page_by_id import GetVisiblePageById
from app.modules.knowledge.application.list_visible_pages import ListVisiblePages
from app.modules.knowledge.infrastructure.sqlalchemy_page_repository import (
    SqlAlchemyPageRepository,
)


def get_list_visible_pages_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ListVisiblePages:
    return ListVisiblePages(SqlAlchemyPageRepository(session))


def get_visible_page_by_id_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GetVisiblePageById:
    return GetVisiblePageById(SqlAlchemyPageRepository(session))
