from uuid import UUID

from app.modules.knowledge.application.errors import (
    InvalidPageLanguageError,
    PageNotFoundError,
)
from app.modules.knowledge.domain.page_repository import PageByIdResult, PageRepository


class GetVisiblePageById:
    def __init__(self, page_repository: PageRepository) -> None:
        self._page_repository = page_repository

    async def execute(
        self,
        user_id: UUID,
        page_id: UUID,
        language_code: str,
    ) -> PageByIdResult:
        normalized_language_code = language_code.strip()
        if not normalized_language_code:
            raise InvalidPageLanguageError("Language code must not be empty")

        page = await self._page_repository.get_visible_page_by_id(
            user_id,
            page_id,
            normalized_language_code,
        )
        if page is None:
            raise PageNotFoundError("Published page not found")
        return page
