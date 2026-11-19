from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.knowledge.application.errors import (
    InvalidPageLanguageError,
    PageNotFoundError,
)
from app.modules.knowledge.application.get_visible_page_by_id import GetVisiblePageById
from app.modules.knowledge.domain.page_repository import PageByIdResult


class FakePageRepository:
    def __init__(self, page: PageByIdResult | None) -> None:
        self.page = page
        self.request: tuple[object, ...] | None = None

    async def get_visible_page_by_id(
        self,
        user_id,
        page_id,
        language_code,
    ) -> PageByIdResult | None:
        self.request = (user_id, page_id, language_code)
        return self.page


def make_page() -> PageByIdResult:
    now = datetime.now(UTC)
    return PageByIdResult(
        id=uuid4(),
        title="Page title",
        template="howto",
        language_code="en",
        tag_ids=(),
        content={"blocks": [{"type": "paragraph", "text": "Page content"}]},
        version_number=3,
        created_at=now,
        updated_at=now,
        published_at=now,
    )


@pytest.mark.asyncio
async def test_get_page_passes_language_and_returns_published_content() -> None:
    user_id = uuid4()
    page = make_page()
    repository = FakePageRepository(page)

    result = await GetVisiblePageById(repository).execute(user_id, page.id, " en ")

    assert repository.request == (user_id, page.id, "en")
    assert result == page
    assert result.content == page.content
    assert result.version_number == 3


@pytest.mark.asyncio
async def test_get_page_raises_not_found_for_missing_or_invisible_page() -> None:
    repository = FakePageRepository(None)

    with pytest.raises(PageNotFoundError):
        await GetVisiblePageById(repository).execute(uuid4(), uuid4(), "en")


@pytest.mark.asyncio
async def test_get_page_rejects_empty_language_code() -> None:
    repository = FakePageRepository(None)

    with pytest.raises(InvalidPageLanguageError):
        await GetVisiblePageById(repository).execute(uuid4(), uuid4(), "  ")

    assert repository.request is None
