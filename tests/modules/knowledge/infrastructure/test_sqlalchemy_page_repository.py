from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.knowledge.domain.enums import TemplateType
from app.modules.knowledge.domain.page_repository import (
    PageByIdResult,
    PageCursor,
    PageListFilters,
    PageListItem,
)
from app.modules.knowledge.infrastructure.sqlalchemy_page_repository import (
    SqlAlchemyPageRepository,
)
from sqlalchemy.dialects import postgresql


class FakeResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> FakeResult:
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows

    def one_or_none(self) -> dict[str, object] | None:
        return self._rows[0] if self._rows else None


class FakeSession:
    def __init__(self, result: FakeResult) -> None:
        self.result = result
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return self.result


@pytest.mark.asyncio
async def test_list_query_enforces_visibility_and_applies_filters_in_sql() -> None:
    now = datetime.now(UTC)
    page_id = uuid4()
    tag_id = uuid4()
    user_id = uuid4()
    session = FakeSession(
        FakeResult(
            [
                {
                    "id": page_id,
                    "title": "Invoice guide",
                    "template": TemplateType.HOWTO,
                    "language_code": "en",
                    "tag_ids": [tag_id],
                    "created_at": now,
                    "updated_at": now,
                    "published_at": now,
                }
            ]
        )
    )

    items = await SqlAlchemyPageRepository(session).list_visible_pages(
        user_id,
        PageListFilters(
            lang="en",
            tags=(tag_id,),
            template="howto",
            q="invoice",
            limit=20,
        ),
        PageCursor(published_at=now, page_id=uuid4()),
    )

    sql = str(session.statement.compile(dialect=postgresql.dialect())).lower()
    assert "user_can_view_page" in sql
    assert "pages.archived_at is null" in sql
    assert "page_versions.state =" in sql
    assert "page_tags" in sql
    assert "ilike" in sql
    assert "page_versions.published_at, pages.id) < (" in sql
    assert "order by page_versions.published_at desc, pages.id desc" in sql
    assert items == [
        PageListItem(
            id=page_id,
            title="Invoice guide",
            template="howto",
            language_code="en",
            tag_ids=(tag_id,),
            created_at=now,
            updated_at=now,
            published_at=now,
        )
    ]


@pytest.mark.asyncio
async def test_get_page_query_returns_visible_published_content_and_version() -> None:
    now = datetime.now(UTC)
    page_id = uuid4()
    tag_id = uuid4()
    user_id = uuid4()
    content = {"blocks": [{"type": "paragraph", "text": "Page content"}]}
    session = FakeSession(
        FakeResult(
            [
                {
                    "id": page_id,
                    "title": "Page title",
                    "template": TemplateType.HOWTO,
                    "language_code": "en",
                    "tag_ids": [tag_id],
                    "content": content,
                    "version_number": 3,
                    "created_at": now,
                    "updated_at": now,
                    "published_at": now,
                }
            ]
        )
    )

    page = await SqlAlchemyPageRepository(session).get_visible_page_by_id(
        user_id,
        page_id,
        "en",
    )

    sql = str(session.statement.compile(dialect=postgresql.dialect())).lower()
    assert "pages.id =" in sql
    assert "page_languages.language_code =" in sql
    assert "user_can_view_page" in sql
    assert "pages.archived_at is null" in sql
    assert "page_versions.state =" in sql
    assert "page_versions.content" in sql
    assert "page_versions.version_number" in sql
    assert page == PageByIdResult(
        id=page_id,
        title="Page title",
        template="howto",
        language_code="en",
        tag_ids=(tag_id,),
        content=content,
        version_number=3,
        created_at=now,
        updated_at=now,
        published_at=now,
    )


@pytest.mark.asyncio
async def test_get_page_query_returns_none_when_page_is_not_visible_or_published() -> (
    None
):
    session = FakeSession(FakeResult([]))

    page = await SqlAlchemyPageRepository(session).get_visible_page_by_id(
        uuid4(),
        uuid4(),
        "en",
    )

    assert page is None
