from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.models import OrgUnit, User


class IdentityRepository(Protocol):
    async def get_user_by_id(self, user_id: str) -> User | None:
        """Return a user by their ID."""
        ...

    async def get_user_by_email(self, email: str) -> User | None:
        """Return a user by their email address."""
        ...

    async def get_org_unit(self, org_unit_id: UUID) -> OrgUnit | None:
        """Return an organizational unit by ID."""
        ...

    async def create_user(
        self,
        *,
        external_id: str,
        email: str,
        full_name: str,
        password_hash: str,
        org_unit_id: UUID,
    ) -> User | None:
        """Insert a user unless the email already exists."""
        ...

    async def update_last_login(self, user: User, logged_in_at: datetime) -> None:
        """Persist the user's latest successful login time."""
        ...
