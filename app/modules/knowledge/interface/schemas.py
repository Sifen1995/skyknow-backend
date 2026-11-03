from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.knowledge.domain.enums import (
    PageVisibility,
    TemplateType,
    VersionState,
)


class PageAudienceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    org_unit_id: UUID
    include_descendants: bool


class PageVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    title: str
    summary: str | None
    content: dict[str, Any]
    content_text: str
    state: VersionState
    created_by: UUID
    approved_by: UUID | None
    published_by: UUID | None
    is_ai_generated: bool
    ai_origin: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    published_at: datetime | None
    scheduled_publish_at: datetime | None
    created_at: datetime


class PageLanguageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    language_code: str
    created_at: datetime
    versions: list[PageVersionResponse]


class PageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template: TemplateType
    owner_org_unit_id: UUID
    owner_id: UUID
    created_by: UUID
    visibility: PageVisibility
    is_customer_visible: bool
    review_interval_months: int | None
    next_review_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    audiences: list[PageAudienceResponse]
    languages: list[PageLanguageResponse]
