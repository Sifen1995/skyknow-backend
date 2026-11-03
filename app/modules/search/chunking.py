import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

DEFAULT_MAX_WORDS = 250
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_WORD_PATTERN = re.compile(r"\S+")
_ANCHOR_PATTERN = re.compile(r"[^\w\s-]", flags=re.UNICODE)


@dataclass(frozen=True)
class Chunk:
    page_version_id: UUID
    page_language_id: UUID
    page_id: UUID
    language_code: str
    chunk_index: int
    heading_path: str
    section_anchor: str | None
    body: str
    token_count: int
    embed_text: str


class VersionForChunking(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def title(self) -> str: ...

    @property
    def content_text(self) -> str: ...


class LanguageForChunking(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def language_code(self) -> str: ...

    @property
    def versions(self) -> Iterable[VersionForChunking]: ...


class PageForChunking(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def languages(self) -> Iterable[LanguageForChunking]: ...


def chunk_pages(
    pages: Iterable[PageForChunking],
    max_words: int = DEFAULT_MAX_WORDS,
) -> list[Chunk]:
    """Split supplied page versions into ordered chunks ready for embedding/storage."""
    _validate_max_words(max_words)
    chunks: list[Chunk] = []

    for page in pages:
        for language in page.languages:
            for version in language.versions:
                heading_and_body_chunks = _chunk_markdown(
                    version.content_text,
                    version.title,
                    max_words,
                )
                for chunk_index, (heading_path, anchor, body) in enumerate(
                    heading_and_body_chunks
                ):
                    chunks.append(
                        Chunk(
                            page_version_id=version.id,
                            page_language_id=language.id,
                            page_id=page.id,
                            language_code=language.language_code,
                            chunk_index=chunk_index,
                            heading_path=heading_path,
                            section_anchor=anchor,
                            body=body,
                            token_count=len(_WORD_PATTERN.findall(body)),
                            embed_text=f"{heading_path}\n{body}",
                        )
                    )

    return chunks


def _chunk_markdown(
    markdown: str,
    title: str,
    max_words: int,
) -> list[tuple[str, str | None, str]]:
    chunks: list[tuple[str, str | None, str]] = []
    heading_stack: list[tuple[int, str]] = []
    section_paragraphs: list[str] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            section_paragraphs.append("\n".join(paragraph_lines))
            paragraph_lines.clear()

    def flush_section() -> None:
        flush_paragraph()
        if not section_paragraphs:
            return

        heading_path = " > ".join([title, *(heading for _, heading in heading_stack)])
        anchor = _slugify(heading_stack[-1][1]) if heading_stack else None
        current: list[str] = []
        current_word_count = 0

        for paragraph in section_paragraphs:
            words = paragraph.split()
            for start in range(0, len(words), max_words):
                piece = " ".join(words[start : start + max_words])
                piece_word_count = len(words[start : start + max_words])
                if current and current_word_count + piece_word_count > max_words:
                    chunks.append((heading_path, anchor, "\n\n".join(current)))
                    current = []
                    current_word_count = 0
                current.append(piece)
                current_word_count += piece_word_count

        if current:
            chunks.append((heading_path, anchor, "\n\n".join(current)))
        section_paragraphs.clear()

    for line in markdown.splitlines():
        heading_match = _HEADING_PATTERN.match(line.strip())
        if heading_match is not None:
            flush_section()
            level = len(heading_match.group(1))
            heading = heading_match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, heading))
        elif line.strip():
            paragraph_lines.append(line.strip())
        else:
            flush_paragraph()

    flush_section()
    return chunks


def _slugify(heading: str) -> str:
    slug = _ANCHOR_PATTERN.sub("", heading.lower())
    return re.sub(r"[\s-]+", "-", slug).strip("-")


def _validate_max_words(max_words: int) -> None:
    if max_words < 1:
        raise ValueError("max_words must be greater than zero")
