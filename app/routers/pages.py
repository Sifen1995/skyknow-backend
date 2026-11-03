from typing import Annotated

from fastapi import APIRouter, Depends

from app.composition.knowledge.wiring import GetAllPages, get_all_pages_use_case
from app.modules.knowledge.interface.schemas import PageResponse

router = APIRouter(prefix="/pages", tags=["Pages"])


@router.get(
    "",
    response_model=list[PageResponse],
    summary="Get all pages",
    description="Returns all database pages, including archived pages and every version state.",
)
async def get_all_pages(
    use_case: Annotated[GetAllPages, Depends(get_all_pages_use_case)],
) -> list[PageResponse]:
    pages = await use_case.execute()
    return [PageResponse.model_validate(page) for page in pages]
