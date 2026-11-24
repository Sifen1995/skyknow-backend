import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.modules.identity.domain.models import TenantRefreshToken
from app.modules.identity.domain.repository import TenantRefreshTokenRecord

logger = logging.getLogger(__name__)


class TenantRefreshTokenStoreError(ApplicationError):
    """Raised when a tenant refresh token write is rejected by the database."""

    status_code = 500
    code = "refresh_token_store_error"


class SqlAlchemyTenantRefreshTokenRepository:
    """SQLAlchemy implementation of TenantRefreshTokenRepository.

    Executes against the active tenant schema set via PostgreSQL search_path.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def store_refresh_token(
        self,
        *,
        family_id: UUID,
        user_id: UUID,
        secret_hash: str,
        expires_at: datetime,
    ) -> None:
        """Insert a new refresh token family row in the tenant schema."""
        self._session.add(
            TenantRefreshToken(
                family_id=family_id,
                user_id=user_id,
                secret_hash=secret_hash,
                expires_at=expires_at,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            logger.error(
                "Failed to store refresh token for user %s: %s",
                user_id,
                exc,
            )
            raise TenantRefreshTokenStoreError(
                "Could not store refresh token — database rejected the write."
            ) from exc

    async def get_refresh_token(
        self, family_id: UUID
    ) -> TenantRefreshTokenRecord | None:
        """Fetch the token family row by family_id in the tenant schema."""
        result = await self._session.execute(
            select(TenantRefreshToken).where(TenantRefreshToken.family_id == family_id)
        )
        token = result.scalar_one_or_none()
        if token is None:
            return None
        return TenantRefreshTokenRecord(
            user_id=token.user_id,
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
        """Atomically increment current_generation and store the new secret hash."""
        result = await self._session.execute(
            update(TenantRefreshToken)
            .where(
                TenantRefreshToken.family_id == family_id,
                TenantRefreshToken.revoked_at.is_(None),
            )
            .values(
                secret_hash=new_secret_hash,
                expires_at=new_expires_at,
                current_generation=TenantRefreshToken.current_generation + 1,
                updated_at=datetime.now(UTC),
            )
            .returning(TenantRefreshToken.current_generation)
        )
        new_generation = result.scalar_one_or_none()
        if new_generation is None:
            raise TenantRefreshTokenStoreError(
                "Refresh token rotation failed — token not found or already revoked."
            )
        return new_generation

    async def revoke_refresh_token(self, family_id: UUID) -> None:
        """Mark a token family as revoked by setting revoked_at."""
        await self._session.execute(
            update(TenantRefreshToken)
            .where(
                TenantRefreshToken.family_id == family_id,
                TenantRefreshToken.revoked_at.is_(None),
            )
            .values(
                revoked_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.commit()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """Revoke all active token families for a user in the tenant schema."""
        await self._session.execute(
            update(TenantRefreshToken)
            .where(
                TenantRefreshToken.user_id == user_id,
                TenantRefreshToken.revoked_at.is_(None),
            )
            .values(
                revoked_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.flush()
