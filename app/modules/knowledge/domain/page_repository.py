from typing import Protocol

from app.modules.knowledge.domain.models import Page


class PageRepository(Protocol):
    async def get_all(self) -> list[Page]:
        """Return every page, including archived pages and all version states."""
        ...
