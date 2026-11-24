import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import GlobalBase


class PlatformAdmin(GlobalBase):
    """The global platform administrators table."""

    __tablename__ = "platform_admins"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(length=150), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(length=255), nullable=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    is_super_superuser: Mapped[bool] = mapped_column(
        Boolean(), server_default=func.false(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlatformAdminRefreshToken(GlobalBase):
    __tablename__ = "platform_admin_refresh_tokens"

    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    platform_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_admins.id", ondelete="CASCADE"),
        nullable=False,
    )
    current_generation: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default="1"
    )
    secret_hash: Mapped[str] = mapped_column(String(length=64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("platform_admin_refresh_tokens_admin_id_idx", "platform_admin_id"),
    )
