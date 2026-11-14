from datetime import UTC, datetime
from uuid import uuid4

from app.modules.identity.application.functionality_usecases.authenticate_access_token import (
    AuthenticatedUser,
)
from fastapi.testclient import TestClient

from app.composition.knowledge.wiring import get_visible_page_by_id_use_case
from app.main import app
from app.modules.knowledge.application.get_visible_page_by_id import GetVisiblePageById
from app.modules.knowledge.domain.page_repository import PageByIdResult
from app.routers.security import require_authenticated_user


class FakePageRepository:
    def __init__(self, page: PageByIdResult) -> None:
        self.page = page

    async def get_visible_page_by_id(
        self,
        user_id,
        page_id,
        language_code,
    ) -> PageByIdResult | None:
        return self.page


def test_get_page_route_returns_content_and_version() -> None:
    now = datetime.now(UTC)
    page_id = uuid4()
    page = PageByIdResult(
        id=page_id,
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

    async def provide_authenticated_user() -> AuthenticatedUser:
        return AuthenticatedUser(user_id=str(uuid4()))

    def provide_get_page_use_case() -> GetVisiblePageById:
        return GetVisiblePageById(FakePageRepository(page))

    app.dependency_overrides[require_authenticated_user] = provide_authenticated_user
    app.dependency_overrides[get_visible_page_by_id_use_case] = (
        provide_get_page_use_case
    )
    try:
        response = TestClient(app).get(f"/api/v1/pages/{page_id}?lang=en")
    finally:
        app.dependency_overrides.pop(require_authenticated_user, None)
        app.dependency_overrides.pop(get_visible_page_by_id_use_case, None)

    assert response.status_code == 200
    assert response.json()["content"] == page.content
    assert response.json()["version_number"] == 3
