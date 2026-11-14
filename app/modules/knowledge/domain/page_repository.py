from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class PageListItem:
    id: UUID
    title: str
    template: str
    language_code: str
    tag_ids: tuple[UUID, ...]
    created_at: datetime
    updated_at: datetime
    published_at: datetime


@dataclass(frozen=True)
class PageListFilters:
    lang: str | None = None
    tags: tuple[UUID, ...] = ()
    template: str | None = None
    q: str | None = None
    limit: int = 20


@dataclass(frozen=True)
class PageCursor:
    published_at: datetime
    page_id: UUID


@dataclass(frozen=True)
class PageListResult:
    items: list[PageListItem]
    next_cursor: str | None
    has_more: bool


@dataclass(frozen=True)
class PageByIdResult:
    id: UUID
    title: str
    template: str
    language_code: str
    tag_ids: tuple[UUID, ...]
    content: dict[str, Any]
    version_number: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime


class PageRepository(Protocol):
    async def list_visible_pages(
        self,
        user_id: UUID,
        filters: PageListFilters,
        cursor: PageCursor | None,
    ) -> list[PageListItem]:
        """Return published page summaries visible to the user plus one lookahead row."""
        ...

    async def get_visible_page_by_id(
        self,
        user_id: UUID,
        page_id: UUID,
        language_code: str,
    ) -> PageByIdResult | None:
        """Return a published page translation only if the user can view the page."""
        ...
