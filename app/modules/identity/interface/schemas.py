from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantLoginRequestBody(BaseModel):
    """Payload for tenant admin authentication."""

    email: str = Field(
        ...,
        min_length=3,
        description="Tenant administrator email address",
        examples=["admin@acme.com"],
    )
    password: str = Field(..., min_length=1, description="Password for authentication")


class TenantUserProfileResponse(BaseModel):
    """User profile details for identity response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: str
    organisation_unit_id: UUID
    status: str
    is_admin: bool = False


class TenantLoginResponse(BaseModel):
    """Response payload for successful tenant admin login."""

    access_token: str
    refresh_token: str
    family_id: UUID
    current_generation: int
    token_type: str = "bearer"
    expires_in: int
    user: TenantUserProfileResponse


class TenantRefreshRequestBody(BaseModel):
    """Payload for rotating a tenant refresh token."""

    family_id: UUID
    count: int = Field(..., ge=1, description="Current generation counter")
    refresh_token: str = Field(
        ..., min_length=1, description="Current raw refresh token"
    )


class TenantRefreshResponse(BaseModel):
    """Response payload for successful tenant token refresh."""

    access_token: str
    refresh_token: str
    family_id: UUID
    current_generation: int
    token_type: str = "bearer"
    expires_in: int


class TenantLogoutRequestBody(BaseModel):
    """Payload for invalidating a tenant refresh token family."""

    family_id: UUID


class TenantLogoutResponse(BaseModel):
    """Response payload for tenant logout."""

    message: str = "Successfully logged out"
