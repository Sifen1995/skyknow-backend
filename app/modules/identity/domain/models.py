import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import TenantBase
from app.modules.identity.domain.enums import IdPType, RoleScope, SystemRole, UserStatus


class Role(TenantBase):
    """System role defined inside a tenant schema."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[SystemRole] = mapped_column(String(50), nullable=False)
    scope: Mapped[RoleScope] = mapped_column(
        String(50), nullable=False, server_default=RoleScope.UNIT_AND_BELOW
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="role")


class IdentityProvider(TenantBase):
    """Identity provider configured for a tenant (standalone, OIDC, SAML, LDAP)."""

    __tablename__ = "identity_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    type: Mapped[IdPType] = mapped_column(String(50), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default="{}", nullable=False
    )
    auto_login_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    identities: Mapped[list["UserIdentity"]] = relationship(
        "UserIdentity", back_populates="identity_provider"
    )


class User(TenantBase):
    """User account within a tenant schema (HOT-optimized)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    organisation_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        String(50), server_default=UserStatus.ACTIVE, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    role: Mapped[Role | None] = relationship(
        "Role", back_populates="users", lazy="joined"
    )
    identities: Mapped[list["UserIdentity"]] = relationship(
        "UserIdentity", back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["TenantRefreshToken"]] = relationship(
        "TenantRefreshToken", back_populates="user", cascade="all, delete-orphan"
    )


class UserIdentity(TenantBase):
    """User credentials / identity links (password hash or external SSO link)."""

    __tablename__ = "user_identities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    identity_provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity_providers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship("User", back_populates="identities")
    identity_provider: Mapped[IdentityProvider] = relationship(
        "IdentityProvider", back_populates="identities"
    )


class TenantRefreshToken(TenantBase):
    """Rotating refresh token row inside a tenant schema."""

    __tablename__ = "refresh_tokens"

    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    current_generation: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")
