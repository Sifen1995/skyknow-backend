import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base
from app.modules.knowledge.domain.enums import (
    PageVisibility,
    ReviewDecision,
    TemplateType,
    VersionState,
)


class Page(Base):
    """The immutable parent container for a knowledge item."""

    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    template: Mapped[TemplateType] = mapped_column(
        ENUM(
            TemplateType,
            name="page_template",
            create_type=False,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )
    owner_org_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    visibility: Mapped[PageVisibility] = mapped_column(
        ENUM(
            PageVisibility,
            name="visibility_scope",
            create_type=False,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        server_default=PageVisibility.RESTRICTED.value,
    )
    is_customer_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    review_interval_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    languages: Mapped[list["PageLanguage"]] = relationship(
        "PageLanguage", back_populates="page", cascade="all, delete-orphan"
    )
    audiences: Mapped[list["PageAudience"]] = relationship(
        "PageAudience", back_populates="page", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "template IN ('howto', 'faq', 'policy')", name="ck_pages_template"
        ),
        CheckConstraint(
            "visibility IN ('restricted', 'all_staff')", name="ck_pages_visibility"
        ),
    )


class PageAudience(Base):
    """Target org units that can view a restricted page."""

    __tablename__ = "page_audiences"

    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), primary_key=True
    )
    org_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_units.id", ondelete="CASCADE"),
        primary_key=True,
    )
    include_descendants: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    page: Mapped["Page"] = relationship("Page", back_populates="audiences")


class PageLanguage(Base):
    """One language translation track for a page."""

    __tablename__ = "page_languages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(
        Text, ForeignKey("languages.code"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    page: Mapped["Page"] = relationship("Page", back_populates="languages")
    versions: Mapped[list["PageVersion"]] = relationship(
        "PageVersion", back_populates="page_language", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "page_id", "language_code", name="uq_page_languages_page_lang"
        ),
    )


class PageVersion(Base):
    """Immutable numbered content versions for a specific page language."""

    __tablename__ = "page_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    page_language_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("page_languages.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[VersionState] = mapped_column(
        ENUM(
            VersionState,
            name="version_state",
            create_type=False,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        server_default=VersionState.DRAFT.value,
    )

    # Audit fields & Workflow tracking
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    is_ai_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    ai_origin: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    page_language: Mapped["PageLanguage"] = relationship(
        "PageLanguage", back_populates="versions"
    )
    reviews: Mapped[list["VersionReview"]] = relationship(
        "VersionReview", back_populates="version"
    )

    __table_args__ = (
        UniqueConstraint(
            "page_language_id", "version_number", name="uq_page_versions_lang_number"
        ),
        CheckConstraint(
            "state IN ('draft', 'in_review', 'approved', 'published', 'archived')",
            name="ck_page_versions_state",
        ),
        # Database constraint: strictly at most ONE published version per language track
        Index(
            "uq_page_versions_one_published",
            "page_language_id",
            unique=True,
            postgresql_where=func.text("state = 'published'"),
        ),
    )


class VersionReview(Base):
    """Review decisions and comments for a version."""

    __tablename__ = "version_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("page_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    decision: Mapped[ReviewDecision] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    version: Mapped["PageVersion"] = relationship(
        "PageVersion", back_populates="reviews"
    )

    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'rejected')", name="ck_version_reviews_decision"
        ),
        # Rejection MUST have a comment
        CheckConstraint(
            "(decision = 'rejected' AND comment IS NOT NULL AND length(trim(comment)) > 0) OR (decision = 'approved')",
            name="ck_version_reviews_rejection_comment",
        ),
    )
