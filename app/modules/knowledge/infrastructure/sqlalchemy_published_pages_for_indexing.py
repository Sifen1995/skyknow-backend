from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.knowledge.application.page_indexing_port import (
    PageLanguageForIndexing,
    PublishedPageForIndexing,
    PublishedVersionForIndexing,
)
from app.modules.knowledge.domain.enums import VersionState
from app.modules.knowledge.domain.models import Page, PageLanguage, PageVersion


class SqlAlchemyPublishedPagesForIndexing:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_published_pages_for_indexing(
        self,
    ) -> list[PublishedPageForIndexing]:
        statement = (
            select(Page)
            .where(
                Page.archived_at.is_(None),
                Page.languages.any(
                    PageLanguage.versions.any(
                        PageVersion.state == VersionState.PUBLISHED
                    )
                ),
            )
            .options(
                selectinload(Page.languages).selectinload(
                    PageLanguage.versions.and_(
                        PageVersion.state == VersionState.PUBLISHED
                    )
                )
            )
            .order_by(Page.created_at, Page.id)
        )
        result = await self._session.execute(statement)

        pages: list[PublishedPageForIndexing] = []
        for page in result.scalars().unique():
            languages = tuple(
                PageLanguageForIndexing(
                    id=language.id,
                    language_code=language.language_code,
                    versions=tuple(
                        PublishedVersionForIndexing(
                            id=version.id,
                            title=version.title,
                            content_text=version.content_text,
                        )
                        for version in language.versions
                    ),
                )
                for language in page.languages
                if language.versions
            )
            if languages:
                pages.append(PublishedPageForIndexing(id=page.id, languages=languages))
        return pages
