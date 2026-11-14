import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.modules.platform_admin.domain.models import PlatformAdminRefreshToken
from app.modules.platform_admin.domain.platform_admin_repository import (
    PlatformAdminRefreshTokenRecord,
)

logger = logging.getLogger(__name__)


class RefreshTokenStoreError(ApplicationError):
    """Raised when a refresh token write is rejected by the database."""

    status_code = 500
    code = "refresh_token_store_error"


class SqlAlchemyPlatformAdminRefreshRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def store_refresh_token(
        self,
        *,
        family_id: UUID,
        platform_admin_id: UUID,
        secret_hash: str,
        expires_at: datetime,
    ) -> None:
        """Insert a new refresh token family row (one row per active family).

        family_id is the PK — the DB server_default sets current_generation = 1.

        Raises:
            RefreshTokenStoreError: on any IntegrityError (duplicate family_id,
                unknown platform_admin_id FK, etc.) so the caller always gets
                a typed domain error instead of a raw SQLAlchemy exception.
        """
        self._session.add(
            PlatformAdminRefreshToken(
                family_id=family_id,
                platform_admin_id=platform_admin_id,
                secret_hash=secret_hash,
                expires_at=expires_at,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            logger.error(
                "Failed to store refresh token for platform admin %s: %s",
                platform_admin_id,
                exc,
            )
            raise RefreshTokenStoreError(
                "Could not store refresh token — database rejected the write."
            ) from exc

    async def get_refresh_token(
        self, family_id: UUID
    ) -> PlatformAdminRefreshTokenRecord | None:
        """Fetch the token family row.

        Returns None when the family_id does not exist.
        """
        result = await self._session.execute(
            select(PlatformAdminRefreshToken).where(
                PlatformAdminRefreshToken.family_id == family_id
            )
        )
        token = result.scalar_one_or_none()
        if token is None:
            return None
        return PlatformAdminRefreshTokenRecord(
            platform_admin_id=token.platform_admin_id,
            family_id=token.family_id,
            current_generation=token.current_generation,
            secret_hash=token.secret_hash,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
        )

    async def get_refresh_token_by_admin_id(
        self, platform_admin_id: UUID
    ) -> PlatformAdminRefreshTokenRecord | None:
        """Fetch an admin's token row."""
        result = await self._session.execute(
            select(PlatformAdminRefreshToken).where(
                PlatformAdminRefreshToken.platform_admin_id == platform_admin_id,
                PlatformAdminRefreshToken.revoked_at.is_(None),
            )
        )
        token = result.scalar_one_or_none()
        if token is None:
            return None
        return PlatformAdminRefreshTokenRecord(
            platform_admin_id=token.platform_admin_id,
            family_id=token.family_id,
            current_generation=token.current_generation,
            secret_hash=token.secret_hash,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
        )

    async def rotate_refresh_token(
        self,
        *,
        family_id: UUID,
        new_secret_hash: str,
        new_expires_at: datetime,
    ) -> int:
        """Atomically increment current_generation and store the new secret hash.

        Single UPDATE … RETURNING round trip — no extra SELECT needed.

        updated_at is set explicitly because SQLAlchemy's onupdate=func.now()
        only fires for ORM unit-of-work flushes, not Core UPDATE statements.

        Returns:
            The new current_generation value after the increment, so the
            use-case can embed it in the token payload for verification on
            the next rotation call.

        Raises:
            RefreshTokenStoreError: when no row was updated, meaning the
                family_id doesn't exist or the token is already revoked.
        """
        result = await self._session.execute(
            update(PlatformAdminRefreshToken)
            .where(
                PlatformAdminRefreshToken.family_id == family_id,
                PlatformAdminRefreshToken.revoked_at.is_(None),
            )
            .values(
                secret_hash=new_secret_hash,
                expires_at=new_expires_at,
                current_generation=PlatformAdminRefreshToken.current_generation + 1,
                updated_at=datetime.now(UTC),
            )
            .returning(PlatformAdminRefreshToken.current_generation)
        )
        new_generation = result.scalar_one_or_none()
        if new_generation is None:
            raise RefreshTokenStoreError(
                "Refresh token rotation failed — token not found or already revoked."
            )
        return new_generation

    async def revoke_refresh_token(self, family_id: UUID) -> None:
        """Mark a token family as revoked by setting revoked_at.

        The WHERE revoked_at IS NULL guard makes this idempotent — revoking
        an already-revoked token is a no-op rather than an error.
        Explicitly commits the transaction so the revocation persists even if
        the caller subsequently raises an HTTP/Application error.
        """
        await self._session.execute(
            update(PlatformAdminRefreshToken)
            .where(
                PlatformAdminRefreshToken.family_id == family_id,
                PlatformAdminRefreshToken.revoked_at.is_(None),
            )
            .values(
                revoked_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.commit()

    async def revoke_all_for_admin(self, platform_admin_id: UUID) -> None:
        """Revoke all active token families for a platform admin."""
        await self._session.execute(
            update(PlatformAdminRefreshToken)
            .where(
                PlatformAdminRefreshToken.platform_admin_id == platform_admin_id,
                PlatformAdminRefreshToken.revoked_at.is_(None),
            )
            .values(
                revoked_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.flush()
