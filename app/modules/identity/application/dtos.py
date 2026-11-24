from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel


class TenantLoginRequest(BaseModel):
    email: str
    password: str


class TenantRefreshRequest(BaseModel):
    family_id: UUID
    count: int
    refresh_token: str


class TenantLogoutRequest(BaseModel):
    family_id: UUID


@dataclass(frozen=True)
class TenantUserProfile:
    id: UUID
    name: str
    email: str
    role: str
    organisation_unit_id: UUID
    status: str
    is_admin: bool = False


@dataclass(frozen=True)
class TenantLoginResult:
    user: TenantUserProfile
    access_token: str
    refresh_token: str
    family_id: UUID
    current_generation: int
    expires_in: int


@dataclass(frozen=True)
class TenantRefreshResult:
    access_token: str
    refresh_token: str
    family_id: UUID
    current_generation: int
    expires_in: int
