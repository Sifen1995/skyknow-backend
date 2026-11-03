from app.modules.knowledge.application.page_indexing_port import (
    PublishedPageForIndexing,
    PublishedPagesForIndexingPort,
)


class GetPublishedPagesForIndexing:
    def __init__(self, port: PublishedPagesForIndexingPort) -> None:
        self._port = port

    async def execute(self) -> list[PublishedPageForIndexing]:
        return await self._port.get_published_pages_for_indexing()
