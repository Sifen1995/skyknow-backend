from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.models import User, UserIdentity


@dataclass(frozen=True)
class RoleRecord:
    id: UUID
    name: str
    scope: str
    description: str | None = None


@dataclass(frozen=True)
class TenantRefreshTokenRecord:
    user_id: UUID
    family_id: UUID
    current_generation: int
    secret_hash: str
    expires_at: datetime
    revoked_at: datetime | None


class TenantUserRepository(Protocol):
    """Port for user accounts within a tenant schema."""

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by email in the active tenant schema."""
        ...

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Fetch a user by ID in the active tenant schema."""
        ...

    async def update_last_login(self, user: User, timestamp: datetime) -> None:
        """Update last_login_at timestamp for a user (HOT update)."""
        ...


class TenantIdentityRepository(Protocol):
    """Port for credentials and identity provider links."""

    async def get_standalone_identity(self, user_id: UUID) -> UserIdentity | None:
        """Fetch local credentials (password hash) for a user."""
        ...

    async def get_identity_by_provider(
        self, identity_provider_id: UUID, provider_user_id: str
    ) -> UserIdentity | None:
        """Fetch user identity link by identity provider."""
        ...


class TenantRefreshTokenRepository(Protocol):
    """Port for rotating refresh tokens within a tenant schema."""

    async def store_refresh_token(
        self,
        *,
        family_id: UUID,
        user_id: UUID,
        secret_hash: str,
        expires_at: datetime,
    ) -> None:
        """Store a new refresh token family for a user."""
        ...

    async def get_refresh_token(
        self, family_id: UUID
    ) -> TenantRefreshTokenRecord | None:
        """Fetch a refresh token record by family ID."""
        ...

    async def rotate_refresh_token(
        self,
        *,
        family_id: UUID,
        new_secret_hash: str,
        new_expires_at: datetime,
    ) -> int:
        """Rotate token secret and increment generation counter."""
        ...

    async def revoke_refresh_token(self, family_id: UUID) -> None:
        """Revoke a token family."""
        ...

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """Revoke all active token families for a user."""
        ...


class TenantRoleRepository(Protocol):
    """Port for role caching and querying within a tenant schema."""

    async def get_by_id(self, role_id: UUID, *, subdomain: str) -> RoleRecord | None:
        """Fetch a role by ID, checking Redis cache first and falling back to DB."""
        ...

    async def get_all(self, *, subdomain: str) -> list[RoleRecord]:
        """Fetch all roles for a tenant, caching them in Redis."""
        ...
