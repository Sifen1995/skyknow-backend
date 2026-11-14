from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.platform_admin.application.dtos import (
    RefreshRequest,
    SuperUserRequest,
)

__all__ = [
    "RefreshRequest",
    "RefreshResponse",
    "SuperUserProfileResponse",
    "SuperUserRequest",
    "SuperUserResponse",
]


class SuperUserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str


class SuperUserResponse(BaseModel):
    access_token: str
    refresh_token: str
    family_id: UUID
    current_generation: int
    token_type: str = "bearer"
    expires_in: int
    admin: SuperUserProfileResponse


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    family_id: UUID
    current_generation: int
    token_type: str = "bearer"
    expires_in: int
