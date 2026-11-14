from uuid import UUID

from sqlalchemy import exists, func, select, tuple_
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.domain.enums import VersionState
from app.modules.knowledge.domain.models import Page, PageLanguage, PageTag, PageVersion
from app.modules.knowledge.domain.page_repository import (
    PageByIdResult,
    PageCursor,
    PageListFilters,
    PageListItem,
)


class SqlAlchemyPageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_visible_pages(
        self,
        user_id: UUID,
        filters: PageListFilters,
        cursor: PageCursor | None,
    ) -> list[PageListItem]:
        tag_ids = func.coalesce(
            func.array_agg(PageTag.tag_id).filter(PageTag.tag_id.is_not(None)),
            array([], type_=PostgreSQLUUID(as_uuid=True)),
        ).label("tag_ids")
        statement = (
            select(
                Page.id.label("id"),
                PageVersion.title.label("title"),
                Page.template.label("template"),
                PageLanguage.language_code.label("language_code"),
                tag_ids,
                Page.created_at.label("created_at"),
                Page.updated_at.label("updated_at"),
                PageVersion.published_at.label("published_at"),
            )
            .select_from(Page)
            .join(PageLanguage, PageLanguage.page_id == Page.id)
            .join(PageVersion, PageVersion.page_language_id == PageLanguage.id)
            .outerjoin(PageTag, PageTag.page_id == Page.id)
            .where(
                Page.archived_at.is_(None),
                PageVersion.state == VersionState.PUBLISHED,
                PageVersion.published_at.is_not(None),
                func.user_can_view_page(user_id, Page.id).is_(True),
            )
            .group_by(
                Page.id,
                PageVersion.title,
                Page.template,
                PageLanguage.language_code,
                Page.created_at,
                Page.updated_at,
                PageVersion.published_at,
            )
        )

        if filters.lang is not None:
            statement = statement.where(PageLanguage.language_code == filters.lang)
        if filters.template is not None:
            statement = statement.where(Page.template == filters.template)
        if filters.q is not None:
            title_query = (
                filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            statement = statement.where(
                PageVersion.title.ilike(f"%{title_query}%", escape="\\")
            )
        if filters.tags:
            matching_tag = exists(
                select(1)
                .select_from(PageTag)
                .where(
                    PageTag.page_id == Page.id,
                    PageTag.tag_id.in_(filters.tags),
                )
                .correlate(Page)
            )
            statement = statement.where(matching_tag)
        if cursor is not None:
            statement = statement.where(
                tuple_(PageVersion.published_at, Page.id)
                < tuple_(cursor.published_at, cursor.page_id)
            )

        statement = statement.order_by(
            PageVersion.published_at.desc(), Page.id.desc()
        ).limit(filters.limit + 1)
        result = await self._session.execute(statement)
        return [
            PageListItem(
                id=row["id"],
                title=row["title"],
                template=getattr(row["template"], "value", row["template"]),
                language_code=row["language_code"],
                tag_ids=tuple(row["tag_ids"] or ()),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                published_at=row["published_at"],
            )
            for row in result.mappings().all()
        ]

    async def get_visible_page_by_id(
        self,
        user_id: UUID,
        page_id: UUID,
        language_code: str,
    ) -> PageByIdResult | None:
        tag_ids = func.coalesce(
            func.array_agg(PageTag.tag_id).filter(PageTag.tag_id.is_not(None)),
            array([], type_=PostgreSQLUUID(as_uuid=True)),
        ).label("tag_ids")
        statement = (
            select(
                Page.id.label("id"),
                PageVersion.title.label("title"),
                Page.template.label("template"),
                PageLanguage.language_code.label("language_code"),
                tag_ids,
                PageVersion.content.label("content"),
                PageVersion.version_number.label("version_number"),
                Page.created_at.label("created_at"),
                Page.updated_at.label("updated_at"),
                PageVersion.published_at.label("published_at"),
            )
            .select_from(Page)
            .join(PageLanguage, PageLanguage.page_id == Page.id)
            .join(PageVersion, PageVersion.page_language_id == PageLanguage.id)
            .outerjoin(PageTag, PageTag.page_id == Page.id)
            .where(
                Page.id == page_id,
                PageLanguage.language_code == language_code,
                Page.archived_at.is_(None),
                PageVersion.state == VersionState.PUBLISHED,
                PageVersion.published_at.is_not(None),
                func.user_can_view_page(user_id, Page.id).is_(True),
            )
            .group_by(
                Page.id,
                PageVersion.title,
                Page.template,
                PageLanguage.language_code,
                PageVersion.content,
                PageVersion.version_number,
                Page.created_at,
                Page.updated_at,
                PageVersion.published_at,
            )
        )
        result = await self._session.execute(statement)
        row = result.mappings().one_or_none()
        if row is None:
            return None

        return PageByIdResult(
            id=row["id"],
            title=row["title"],
            template=getattr(row["template"], "value", row["template"]),
            language_code=row["language_code"],
            tag_ids=tuple(row["tag_ids"] or ()),
            content=row["content"],
            version_number=row["version_number"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            published_at=row["published_at"],
        )
