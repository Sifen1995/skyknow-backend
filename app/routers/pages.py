from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.composition.knowledge.wiring import (
    get_list_visible_pages_use_case,
    get_visible_page_by_id_use_case,
)
from app.modules.knowledge.application.get_visible_page_by_id import GetVisiblePageById
from app.modules.knowledge.application.list_visible_pages import (
    ListVisiblePages,
    PageListQuery,
)
from app.modules.knowledge.interface.schemas import (
    PageByIdResponse,
    PageListItemResponse,
    PageListResponse,
)
from app.routers.security import AuthenticatedUser, require_authenticated_user

router = APIRouter(prefix="/pages", tags=["Pages"])
CurrentUser = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


@router.get(
    "",
    response_model=PageListResponse,
    summary="List published pages visible to the authenticated user",
    description=(
        "Returns summary fields for non-archived published pages the user is "
        "allowed to view. Results use a stable cursor ordered by publication time."
    ),
)
async def list_visible_pages(
    current_user: CurrentUser,
    use_case: Annotated[ListVisiblePages, Depends(get_list_visible_pages_use_case)],
    lang: str | None = None,
    tag: Annotated[list[UUID] | None, Query()] = None,
    template: str | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> PageListResponse:
    result = await use_case.execute(
        UUID(current_user.user_id),
        PageListQuery(
            lang=lang,
            tags=tuple(tag or ()),
            template=template,
            q=q,
            limit=limit,
            cursor=cursor,
        ),
    )
    return PageListResponse(
        items=[PageListItemResponse.model_validate(item) for item in result.items],
        next_cursor=result.next_cursor,
        has_more=result.has_more,
    )


@router.get(
    "/{page_id}",
    response_model=PageByIdResponse,
    summary="Get a published page",
    description=(
        "Returns the requested published language version, including its content, "
        "only when the authenticated user can view the page."
    ),
)
async def get_visible_page_by_id(
    page_id: UUID,
    current_user: CurrentUser,
    use_case: Annotated[
        GetVisiblePageById,
        Depends(get_visible_page_by_id_use_case),
    ],
    lang: Annotated[str, Query(min_length=1)],
) -> PageByIdResponse:
    result = await use_case.execute(
        UUID(current_user.user_id),
        page_id,
        lang,
    )
    return PageByIdResponse.model_validate(result)
