from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    full_name: str
    telecom_id: str
    email: str
    password: str
    org_unit_id: str


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str
    org_unit_id: UUID


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutRequest(BaseModel):
    refresh_token: str


class RegisterResponse(UserProfileResponse):
    pass
