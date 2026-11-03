from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class PublishedVersionForIndexing:
    id: UUID
    title: str
    content_text: str


@dataclass(frozen=True)
class PageLanguageForIndexing:
    id: UUID
    language_code: str
    versions: tuple[PublishedVersionForIndexing, ...]


@dataclass(frozen=True)
class PublishedPageForIndexing:
    id: UUID
    languages: tuple[PageLanguageForIndexing, ...]


class PublishedPagesForIndexingPort(Protocol):
    async def get_published_pages_for_indexing(
        self,
    ) -> list[PublishedPageForIndexing]:
        """Return active pages with published version text needed for indexing."""
        ...
