from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.composition.database import get_db
from app.modules.knowledge.application.page_service import GetAllPages
from app.modules.knowledge.infrastructure.sqlalchemy_page_repository import (
    SqlAlchemyPageRepository,
)


def get_all_pages_use_case(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GetAllPages:
    return GetAllPages(SqlAlchemyPageRepository(session))
