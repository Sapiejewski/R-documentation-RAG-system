"""Turn extracted help pages into retrieval chunks.

Every chunk starts with a short header (`package::topic - title`, plus aliases) so
it makes sense on its own when the LLM later sees it without the rest of the page.
Chunks stay under `max_chars`: sections are packed together while they fit, long
sections are split on blank lines, then on single lines. Examples are kept apart
from the prose, since they are code and answer different questions.
"""

import re
import uuid
from dataclasses import dataclass

from rag.ingestion.rdtext import parse_sections

# Fixed namespace, so the same topic always maps to the same point id.
_NAMESPACE = uuid.UUID("5d3f6a0e-8c52-4a71-b0a4-2f8d3c9e6b17")
_DROPPED_SECTIONS = {"Author(s)", "Author", "Authors"}
_EXAMPLES = "Examples"
_MAX_ALIASES_IN_HEADER = 12


@dataclass(frozen=True)
class Chunk:
    id: str
    package: str
    version: str
    topic: str
    title: str
    aliases: tuple[str, ...]
    section: str
    index: int
    count: int
    text: str

    def payload(self) -> dict:
        return {
            "package": self.package,
            "version": self.version,
            "topic": self.topic,
            "title": self.title,
            "aliases": list(self.aliases),
            "section": self.section,
            "chunk_index": self.index,
            "chunk_count": self.count,
            "text": self.text,
        }


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [str(item) for item in value if str(item)]


def _hard_split(line: str, limit: int) -> list[str]:
    """Cut one over-long line at spaces (or mid-word if there are none)."""
    pieces = []
    while len(line) > limit:
        cut = line.rfind(" ", 0, limit)
        cut = cut if cut > 0 else limit
        pieces.append(line[:cut])
        line = line[cut:].lstrip()
    if line:
        pieces.append(line)
    return pieces


def _pack(pieces: list[str], limit: int, separator: str) -> list[str]:
    """Greedily join pieces (each already <= limit) into blocks <= limit."""
    blocks: list[str] = []
    current = ""
    for piece in pieces:
        if not current:
            current = piece
        elif len(current) + len(separator) + len(piece) <= limit:
            current += separator + piece
        else:
            blocks.append(current)
            current = piece
    if current:
        blocks.append(current)
    return blocks


def split_text(text: str, limit: int) -> list[str]:
    """Split text into blocks of at most `limit` characters.

    Prefers paragraph boundaries (blank lines), then line boundaries.
    """
    if len(text) <= limit:
        return [text]
    pieces: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        if len(paragraph) <= limit:
            pieces.append(paragraph)
            continue
        lines: list[str] = []
        for line in paragraph.split("\n"):
            lines.extend(_hard_split(line, limit) if len(line) > limit else [line])
        pieces.extend(_pack(lines, limit, "\n"))
    return _pack(pieces, limit, "\n\n")


def _make_chunks(
    package: str,
    version: str,
    topic: str,
    title: str,
    aliases: tuple[str, ...],
    header: str,
    bodies: list[tuple[str, str]],
) -> list[Chunk]:
    chunks = []
    for index, (section, body) in enumerate(bodies):
        chunks.append(
            Chunk(
                id=str(uuid.uuid5(_NAMESPACE, f"{package}/{topic}/{index}")),
                package=package,
                version=version,
                topic=topic,
                title=title,
                aliases=aliases,
                section=section,
                index=index,
                count=len(bodies),
                text=f"{header}\n\n{body}",
            )
        )
    return chunks


def chunk_topic(record: dict, max_chars: int = 1500) -> list[Chunk]:
    """Chunk one help topic (a `type: topic` record from the extraction step)."""
    package = record["package"]
    version = record.get("version") or ""
    topic = record["name"]
    title = record.get("title") or ""
    aliases = tuple(dict.fromkeys(_as_list(record.get("aliases"))))

    header = f"{package}::{topic}" + (f" - {title}" if title else "")
    if len(aliases) > 1:
        header += "\nAliases: " + ", ".join(aliases[:_MAX_ALIASES_IN_HEADER])
    budget = max(200, max_chars - len(header) - 2)

    sections = [s for s in parse_sections(record.get("text") or "") if s.title not in _DROPPED_SECTIONS]
    prose = [s for s in sections if s.title != _EXAMPLES]
    examples = [s for s in sections if s.title == _EXAMPLES]

    # Prose: one unit per section (long sections split), then packed into chunks.
    units: list[tuple[str, str]] = []
    for section in prose:
        room = budget - len(section.title) - 2
        for piece in split_text(section.body, room):
            units.append((section.title, f"{section.title}:\n{piece}"))

    bodies: list[tuple[str, str]] = []
    labels: list[str] = []
    current = ""
    for label, text in units:
        if current and len(current) + 2 + len(text) > budget:
            bodies.append((", ".join(dict.fromkeys(labels)), current))
            labels, current = [], ""
        current = f"{current}\n\n{text}" if current else text
        labels.append(label)
    if current:
        bodies.append((", ".join(dict.fromkeys(labels)), current))

    # Examples: separate chunks.
    for section in examples:
        room = budget - len(_EXAMPLES) - 2
        for piece in split_text(section.body, room):
            bodies.append((_EXAMPLES, f"{_EXAMPLES}:\n{piece}"))

    return _make_chunks(package, version, topic, title, aliases, header, bodies)


def chunk_description(record: dict, max_chars: int = 1500) -> list[Chunk]:
    """Chunk the package-level description (a `type: description` record)."""
    package = record["package"]
    title = record.get("title") or ""
    description = record.get("description") or ""
    if not (title or description):
        return []
    header = f"{package} (package overview)" + (f" - {title}" if title else "")
    bodies = [("Description", f"Description:\n{piece}") for piece in split_text(description, max_chars - len(header))]
    return _make_chunks(
        package, record.get("version") or "", f"{package}-description", title, (package,), header, bodies
    )


def chunk_record(record: dict, max_chars: int = 1500) -> list[Chunk]:
    kind = record.get("type", "topic")
    if kind == "topic":
        return chunk_topic(record, max_chars)
    if kind == "description":
        return chunk_description(record, max_chars)
    return []
