from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class PlatformAdminRefreshTokenRecord:
    platform_admin_id: UUID
    family_id: UUID
    current_generation: int
    secret_hash: str
    expires_at: datetime
    revoked_at: datetime | None


class PlatformAdminRepository(Protocol):
    async def get_platform_admin_by_email(self, email: str) -> Any | None:
        """Return a platform admin by their email address."""
        ...

    async def create_platform_admin(
        self,
        *,
        name: str,
        email: str,
        password_hash: str,
        is_super_superuser: bool = False,
    ) -> Any | None:
        """Insert a platform admin unless the email already exists."""
        ...

    async def get_platform_admin_by_id(self, platform_admin_id: UUID) -> Any | None:
        """Return a platform admin by their ID."""
        ...

    async def update_last_login(self, admin: Any, logged_in_at: datetime) -> None:
        """Update last_login_at timestamp for a platform admin."""
        ...


class PlatformAdminRefreshTokenRepository(Protocol):
    async def store_refresh_token(
        self,
        *,
        family_id: UUID,
        platform_admin_id: UUID,
        secret_hash: str,
        expires_at: datetime,
    ) -> None:
        """Insert a new refresh token family row for a platform admin.

        family_id is the primary key — one row per active token family.
        current_generation defaults to 1 at the DB level.
        """
        ...

    async def get_refresh_token(
        self, family_id: UUID
    ) -> PlatformAdminRefreshTokenRecord | None:
        """Fetch the token family row."""
        ...

    async def get_refresh_token_by_admin_id(
        self, platform_admin_id: UUID
    ) -> PlatformAdminRefreshTokenRecord | None:
        """Fetch an admin's token row."""
        ...

    async def rotate_refresh_token(
        self,
        *,
        family_id: UUID,
        new_secret_hash: str,
        new_expires_at: datetime,
    ) -> int:
        """Atomically increment current_generation and store the new secret hash.

        Called on every successful token refresh:
          1. Client presents refresh token for the current generation.
          2. Use-case verifies secret_hash matches; calls this method.
          3. DB increments current_generation and writes new_secret_hash.
          4. Use-case issues the new raw token to the client.

        Returns:
            The new current_generation value after the increment, so the
            use-case can embed it in the issued token for next-rotation
            verification.
        """
        ...

    async def revoke_refresh_token(self, family_id: UUID) -> None:
        """Mark a token family as revoked (sets revoked_at)."""
        ...

    async def revoke_all_for_admin(self, platform_admin_id: UUID) -> None:
        """Revoke all active token families for a platform admin."""
        ...
