from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.knowledge.domain.enums import TemplateType


class PageListItemResponse(BaseModel):
    title: str
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template: TemplateType
    language_code: str
    tag_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
    published_at: datetime


class PageListResponse(BaseModel):
    items: list[PageListItemResponse]
    next_cursor: str | None
    has_more: bool


class PageByIdResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    template: TemplateType
    language_code: str
    tag_ids: list[UUID]
    content: dict[str, object]
    version_number: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime
