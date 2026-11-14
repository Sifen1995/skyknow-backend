from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.knowledge.application.errors import InvalidPageListRequestError
from app.modules.knowledge.application.list_visible_pages import (
    ListVisiblePages,
    PageListQuery,
)
from app.modules.knowledge.domain.page_repository import (
    PageCursor,
    PageListFilters,
    PageListItem,
)


class FakePageRepository:
    def __init__(self, rows: list[PageListItem]) -> None:
        self.rows = rows
        self.filters: PageListFilters | None = None
        self.cursor: PageCursor | None = None
        self.user_id = None

    async def list_visible_pages(
        self,
        user_id,
        filters: PageListFilters,
        cursor: PageCursor | None,
    ) -> list[PageListItem]:
        self.user_id = user_id
        self.filters = filters
        self.cursor = cursor
        return self.rows


def make_item(published_at: datetime) -> PageListItem:
    return PageListItem(
        id=uuid4(),
        title="Invoice instructions",
        template="howto",
        language_code="en",
        tag_ids=(),
        created_at=published_at,
        updated_at=published_at,
        published_at=published_at,
    )


@pytest.mark.asyncio
async def test_list_normalizes_filters_and_returns_lookahead_cursor() -> None:
    now = datetime.now(UTC)
    rows = [make_item(now - timedelta(minutes=index)) for index in range(3)]
    repository = FakePageRepository(rows)
    user_id = uuid4()
    tag_id = uuid4()

    result = await ListVisiblePages(repository).execute(
        user_id,
        PageListQuery(
            lang=" en ",
            tags=(tag_id, tag_id),
            template="howto",
            q=" invoice ",
            limit=2,
        ),
    )

    assert repository.user_id == user_id
    assert repository.filters == PageListFilters(
        lang="en",
        tags=(tag_id,),
        template="howto",
        q="invoice",
        limit=2,
    )
    assert result.items == rows[:2]
    assert result.has_more is True
    assert result.next_cursor is not None

    second_repository = FakePageRepository([rows[2]])
    second_result = await ListVisiblePages(second_repository).execute(
        user_id,
        PageListQuery(limit=2, cursor=result.next_cursor),
    )
    assert second_repository.cursor == PageCursor(rows[1].published_at, rows[1].id)
    assert second_result.items == [rows[2]]
    assert second_result.has_more is False
    assert second_result.next_cursor is None


@pytest.mark.asyncio
async def test_list_rejects_invalid_limit_and_cursor() -> None:
    use_case = ListVisiblePages(FakePageRepository([]))

    with pytest.raises(InvalidPageListRequestError):
        await use_case.execute(uuid4(), PageListQuery(limit=101))
    with pytest.raises(InvalidPageListRequestError):
        await use_case.execute(uuid4(), PageListQuery(cursor="invalid-cursor"))
