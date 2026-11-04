"""Read extracted help pages, chunk them, embed them and store them."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rag.chunking import Chunk, chunk_record
from rag.stores import Point, VectorStore


@dataclass(frozen=True)
class IndexReport:
    package: str
    topics: int
    chunks: int
    duplicate_topics: int
    seconds: float


def extracted_path(data_dir: Path, package: str) -> Path:
    return data_dir / "extracted" / f"{package}.jsonl"


def read_records(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found. Extract the package first: make extract PKG={path.stem}")
    records = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{number}: invalid JSON ({error})") from error
    return records


def build_chunks(records: list[dict], max_chars: int = 1500) -> tuple[list[Chunk], int]:
    """Chunk every record. Returns (chunks, number of duplicate topic names skipped)."""
    chunks: list[Chunk] = []
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    for record in records:
        key = (record.get("type", "topic"), record.get("name", ""))
        if key[0] == "topic" and key in seen:
            duplicates += 1
            continue
        seen.add(key)
        chunks.extend(chunk_record(record, max_chars))
    return chunks, duplicates


def index_package(
    package: str,
    *,
    data_dir: Path,
    embedder,
    store: VectorStore,
    max_chars: int = 1500,
    log: Callable[[str], None] = print,
) -> IndexReport:
    """(Re)index one package. Re-running replaces what was stored for it, so
    removed help pages do not linger and nothing is duplicated."""
    started = time.monotonic()
    records = read_records(extracted_path(data_dir, package))
    chunks, duplicates = build_chunks(records, max_chars)
    if not chunks:
        raise ValueError(f"No chunks produced for '{package}'. Is the extracted file empty?")

    log(f"{package}: {len(chunks)} chunks from {len(records)} records, embedding ...")
    # Embed first: if this fails, the previously indexed version is left untouched.
    vectors = embedder.embed_documents([chunk.text for chunk in chunks])

    store.ensure_collection(len(vectors[0]))
    store.delete_package(package)
    store.upsert([Point(c.id, v, c.payload()) for c, v in zip(chunks, vectors)])

    topics = len({c.topic for c in chunks})
    return IndexReport(package, topics, len(chunks), duplicates, time.monotonic() - started)
