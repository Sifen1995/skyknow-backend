from app.modules.knowledge.domain.models import Page
from app.modules.knowledge.domain.page_repository import PageRepository


class GetAllPages:
    def __init__(self, page_repository: PageRepository) -> None:
        self._page_repository = page_repository

    async def execute(self) -> list[Page]:
        return await self._page_repository.get_all()
