from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain.models import IdentityRefreshToken
from app.modules.identity.domain.refresh_token_repository import RefreshTokenRecord


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        family_id: UUID,
        expires_at: datetime,
    ) -> None:
        self._session.add(
            IdentityRefreshToken(
                token_hash=token_hash,
                user_id=user_id,
                family_id=family_id,
                expires_at=expires_at,
            )
        )
        await self._session.flush()

    async def get_for_update(self, token_hash: str) -> RefreshTokenRecord | None:
        result = await self._session.execute(
            select(IdentityRefreshToken)
            .where(IdentityRefreshToken.token_hash == token_hash)
            .with_for_update()
        )
        token = result.scalar_one_or_none()
        if token is None:
            return None
        return RefreshTokenRecord(
            user_id=token.user_id,
            family_id=token.family_id,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
        )

    async def revoke(self, token_hash: str) -> None:
        await self._session.execute(
            update(IdentityRefreshToken)
            .where(
                IdentityRefreshToken.token_hash == token_hash,
                IdentityRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )

    async def revoke_family(self, family_id: UUID) -> None:
        await self._session.execute(
            update(IdentityRefreshToken)
            .where(
                IdentityRefreshToken.family_id == family_id,
                IdentityRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
