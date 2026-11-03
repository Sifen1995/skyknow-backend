import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    Uuid,
    delete,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import ENUM

from app.ai_gateway.embeddings import OpenAIEmbeddingClient
from app.config import settings
from app.core.db import AsyncSessionLocal, async_engine
from app.modules.search.chunking import chunk_pages

_metadata = MetaData()
_pages = Table(
    "pages",
    _metadata,
    Column("id", Uuid, primary_key=True),
    Column("archived_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
_page_languages = Table(
    "page_languages",
    _metadata,
    Column("id", Uuid, primary_key=True),
    Column("page_id", Uuid, nullable=False),
    Column("language_code", Text, nullable=False),
)
_page_versions = Table(
    "page_versions",
    _metadata,
    Column("id", Uuid, primary_key=True),
    Column("page_language_id", Uuid, nullable=False),
    Column("title", Text, nullable=False),
    Column("content_text", Text, nullable=False),
    Column(
        "state",
        ENUM(
            "draft",
            "in_review",
            "approved",
            "published",
            "archived",
            name="version_state",
            create_type=False,
        ),
        nullable=False,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
_chunks = Table(
    "chunks",
    _metadata,
    Column("page_version_id", Uuid, nullable=False),
    Column("page_language_id", Uuid, nullable=False),
    Column("page_id", Uuid, nullable=False),
    Column("language_code", Text, nullable=False),
    Column("chunk_index", Integer, nullable=False),
    Column("heading_path", Text, nullable=False),
    Column("section_anchor", Text),
    Column("body", Text, nullable=False),
    Column("token_count", Integer, nullable=False),
    Column("embedding", Vector(settings.EMBEDDING_DIMS), nullable=False),
    Column("embedding_model", Text, nullable=False),
)


@dataclass
class _VersionForChunking:
    id: UUID
    title: str
    content_text: str


@dataclass
class _LanguageForChunking:
    id: UUID
    language_code: str
    versions: list[_VersionForChunking] = field(default_factory=list)


@dataclass
class _PageForChunking:
    id: UUID
    languages: list[_LanguageForChunking] = field(default_factory=list)
    _languages_by_id: dict[UUID, _LanguageForChunking] = field(
        default_factory=dict,
        repr=False,
    )

    def get_or_add_language(
        self,
        language_id: UUID,
        language_code: str,
    ) -> _LanguageForChunking:
        language = self._languages_by_id.get(language_id)
        if language is None:
            language = _LanguageForChunking(
                id=language_id,
                language_code=language_code,
            )
            self._languages_by_id[language_id] = language
            self.languages.append(language)
        return language


async def _fetch_published_pages() -> list[_PageForChunking]:
    statement = (
        select(
            _pages.c.id.label("page_id"),
            _page_languages.c.id.label("page_language_id"),
            _page_languages.c.language_code,
            _page_versions.c.id.label("page_version_id"),
            _page_versions.c.title,
            _page_versions.c.content_text,
        )
        .select_from(
            _pages.join(
                _page_languages,
                _page_languages.c.page_id == _pages.c.id,
            ).join(
                _page_versions,
                _page_versions.c.page_language_id == _page_languages.c.id,
            )
        )
        .where(
            _pages.c.archived_at.is_(None),
            _page_versions.c.state == "published",
        )
        .order_by(
            _pages.c.created_at,
            _pages.c.id,
            _page_languages.c.language_code,
            _page_versions.c.created_at,
            _page_versions.c.id,
        )
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(statement)

    pages_by_id: dict[UUID, _PageForChunking] = {}
    for row in result.mappings():
        page_id: UUID = row["page_id"]
        page = pages_by_id.setdefault(page_id, _PageForChunking(id=page_id))
        language = page.get_or_add_language(
            row["page_language_id"],
            row["language_code"],
        )
        language.versions.append(
            _VersionForChunking(
                id=row["page_version_id"],
                title=row["title"],
                content_text=row["content_text"],
            )
        )

    return list(pages_by_id.values())


async def backfill_chunks() -> None:
    embedder = OpenAIEmbeddingClient()
    try:
        pages = await _fetch_published_pages()

        chunks = chunk_pages(pages)
        embeddings = await embedder.embed_documents(
            [chunk.embed_text for chunk in chunks]
        )
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding client returned {len(embeddings)} vectors for "
                f"{len(chunks)} chunks"
            )

        page_version_ids = [
            version.id
            for page in pages
            for language in page.languages
            for version in language.versions
        ]
        async with AsyncSessionLocal() as session:
            if page_version_ids:
                await session.execute(
                    delete(_chunks).where(
                        _chunks.c.page_version_id.in_(page_version_ids)
                    )
                )
            if chunks:
                await session.execute(
                    insert(_chunks),
                    [
                        {
                            "page_version_id": chunk.page_version_id,
                            "page_language_id": chunk.page_language_id,
                            "page_id": chunk.page_id,
                            "language_code": chunk.language_code,
                            "chunk_index": chunk.chunk_index,
                            "heading_path": chunk.heading_path,
                            "section_anchor": chunk.section_anchor,
                            "body": chunk.body,
                            "token_count": chunk.token_count,
                            "embedding": embedding,
                            "embedding_model": embedder.model,
                        }
                        for chunk, embedding in zip(chunks, embeddings, strict=True)
                    ],
                )
            await session.commit()

        print(
            f"Backfilled {len(chunks)} chunks from "
            f"{len(page_version_ids)} published page versions."
        )
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(backfill_chunks())
