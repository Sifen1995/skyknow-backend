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
    csrf_token: str
    user: UserProfileResponse


class CsrfResponse(BaseModel):
    csrf_token: str


class RegisterResponse(UserProfileResponse):
    pass
