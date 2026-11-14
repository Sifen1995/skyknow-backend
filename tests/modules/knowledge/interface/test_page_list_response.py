from datetime import UTC, datetime
from uuid import uuid4

from app.modules.knowledge.domain.page_repository import (
    PageByIdResult,
    PageListItem,
    PageListResult,
)
from app.modules.knowledge.interface.schemas import (
    PageByIdResponse,
    PageListItemResponse,
    PageListResponse,
)


def test_page_list_response_maps_application_dataclasses() -> None:
    published_at = datetime.now(UTC)
    item = PageListItem(
        id=uuid4(),
        title="Published guide",
        template="howto",
        language_code="en",
        tag_ids=(),
        created_at=published_at,
        updated_at=published_at,
        published_at=published_at,
    )
    result = PageListResult(items=[item], next_cursor=None, has_more=False)

    response = PageListResponse(
        items=[PageListItemResponse.model_validate(page) for page in result.items],
        next_cursor=result.next_cursor,
        has_more=result.has_more,
    )

    assert response.items[0].id == item.id
    assert response.items[0].title == item.title
    assert response.has_more is False


def test_page_by_id_response_includes_content_and_version() -> None:
    now = datetime.now(UTC)
    page = PageByIdResult(
        id=uuid4(),
        title="Published guide",
        template="howto",
        language_code="en",
        tag_ids=(),
        content={"blocks": [{"type": "paragraph", "text": "Page content"}]},
        version_number=3,
        created_at=now,
        updated_at=now,
        published_at=now,
    )

    response = PageByIdResponse.model_validate(page)

    assert response.content == page.content
    assert response.version_number == 3
