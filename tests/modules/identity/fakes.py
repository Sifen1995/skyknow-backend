from datetime import datetime
from uuid import UUID

from app.modules.identity.domain.models import OrgUnit, User


class FakeIdentityRepository:
    def __init__(
        self,
        *,
        user: User | None = None,
        org_unit: OrgUnit | None = None,
        created_user: User | None = None,
    ) -> None:
        self.user = user
        self.org_unit = org_unit
        self.created_user = created_user
        self.looked_up_emails: list[str] = []
        self.created_user_values: dict[str, object] | None = None
        self.last_login_update: User | None = None
        self.last_login_at: datetime | None = None

    async def get_user_by_id(self, user_id: str) -> User | None:
        if self.user is not None and str(self.user.id) == user_id:
            return self.user
        return None

    async def get_user_by_email(self, email: str) -> User | None:
        self.looked_up_emails.append(email)
        if self.user is not None and self.user.email == email:
            return self.user
        return None

    async def get_org_unit(self, org_unit_id: UUID) -> OrgUnit | None:
        if self.org_unit is not None and self.org_unit.id == org_unit_id:
            return self.org_unit
        return None

    async def create_user(
        self,
        *,
        external_id: str,
        email: str,
        full_name: str,
        password_hash: str,
        org_unit_id: UUID,
    ) -> User | None:
        self.created_user_values = {
            "external_id": external_id,
            "email": email,
            "full_name": full_name,
            "password_hash": password_hash,
            "org_unit_id": org_unit_id,
        }
        return self.created_user

    async def update_last_login(self, user: User, logged_in_at: datetime) -> None:
        self.last_login_update = user
        self.last_login_at = logged_in_at
