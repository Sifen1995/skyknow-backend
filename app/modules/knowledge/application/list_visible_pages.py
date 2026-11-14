import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.knowledge.application.errors import InvalidPageListRequestError
from app.modules.knowledge.domain.enums import TemplateType
from app.modules.knowledge.domain.page_repository import (
    PageCursor,
    PageListFilters,
    PageListItem,
    PageListResult,
    PageRepository,
)


@dataclass(frozen=True)
class PageListQuery:
    lang: str | None = None
    tags: tuple[UUID, ...] = ()
    template: str | None = None
    q: str | None = None
    limit: int = 20
    cursor: str | None = None


class ListVisiblePages:
    def __init__(self, page_repository: PageRepository) -> None:
        self._page_repository = page_repository

    async def execute(
        self,
        user_id: UUID,
        request: PageListQuery,
    ) -> PageListResult:
        normalized_filters = self._validate_filters(
            PageListFilters(
                lang=request.lang,
                tags=request.tags,
                template=request.template,
                q=request.q,
                limit=request.limit,
            )
        )
        page_cursor = (
            self._decode_cursor(request.cursor) if request.cursor is not None else None
        )
        rows = await self._page_repository.list_visible_pages(
            user_id,
            normalized_filters,
            page_cursor,
        )

        has_more = len(rows) > normalized_filters.limit
        items = rows[: normalized_filters.limit]
        next_cursor = self._encode_cursor(items[-1]) if has_more and items else None
        return PageListResult(items, next_cursor, has_more)

    @staticmethod
    def _validate_filters(filters: PageListFilters) -> PageListFilters:
        if not 1 <= filters.limit <= 100:
            raise InvalidPageListRequestError("Limit must be between 1 and 100")

        language = filters.lang.strip() if filters.lang is not None else None
        query = filters.q.strip() if filters.q is not None else None
        template = filters.template
        if template is not None and template not in {
            item.value for item in TemplateType
        }:
            raise InvalidPageListRequestError("Unsupported page template")
        if query is not None and len(query) > 200:
            raise InvalidPageListRequestError(
                "Search query cannot exceed 200 characters"
            )

        return PageListFilters(
            lang=language or None,
            tags=tuple(dict.fromkeys(filters.tags)),
            template=template,
            q=query or None,
            limit=filters.limit,
        )

    @staticmethod
    def _encode_cursor(item: PageListItem) -> str:
        payload = json.dumps(
            {
                "published_at": item.published_at.astimezone(UTC).isoformat(),
                "page_id": str(item.id),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> PageCursor:
        try:
            if not cursor or len(cursor) > 512:
                raise ValueError
            encoded = cursor.encode("ascii")
            payload = base64.b64decode(
                encoded + b"=" * (-len(encoded) % 4),
                altchars=b"-_",
                validate=True,
            )
            data = json.loads(payload)
            published_at = datetime.fromisoformat(data["published_at"])
            page_id = UUID(data["page_id"])
            if published_at.tzinfo is None:
                raise ValueError
        except (
            binascii.Error,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise InvalidPageListRequestError("Cursor is invalid") from exc

        return PageCursor(published_at.astimezone(UTC), page_id)
