import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import GlobalBase


class Tenant(GlobalBase):
    """Global tenant metadata stored in the public schema."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(length=150), nullable=False)
    subdomain: Mapped[str] = mapped_column(
        String(length=64), unique=True, nullable=False
    )
    custom_domain: Mapped[str | None] = mapped_column(
        String(length=255), unique=True, nullable=True
    )
    hosting_mode: Mapped[str] = mapped_column(
        String(length=32), server_default="shared", nullable=False
    )
    primary_color: Mapped[str | None] = mapped_column(String(length=32), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(length=500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(length=32), server_default="active", nullable=False
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
