from uuid import UUID

from pydantic import BaseModel


class SuperUserRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    family_id: UUID
    count: int
    refresh_token: str
