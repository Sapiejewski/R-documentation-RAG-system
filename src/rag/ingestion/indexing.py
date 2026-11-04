"""Keeping the index in step with installed packages.

A sync of one R library is a short conversation with the R client:

1. `plan(manifest)`   the client says what is installed; we drop packages that disappeared and
                      answer which ones to send (new, reinstalled, or indexed in an old format).
2. `begin(...)`       per package to send: clear leftovers of an interrupted earlier attempt,
                      store the package overview.
3. `add_pages(...)`   the help pages, in batches.
4. `commit(...)`      switch searches over to the new version and delete the old one.

Each package version is stored as its own *generation* of points, inactive until `commit`.
Search only sees active points, so it never mixes two versions, and an interrupted transfer
leaves the previous version in place (the registry still names it, so the next sync asks again).

Embeddings are the expensive step, so a chunk whose text was already embedded (same
`content_hash`, e.g. an unchanged page of the previous version) reuses the stored vector.
"""

import hashlib
import logging
import time
import uuid
from collections.abc import Sequence
from typing import Protocol

from rag.ingestion.chunking import CHUNKER_VERSION, Chunk, chunk_description, chunk_topic
from rag.ingestion.registry import PackageRegistry
from rag.retrieval.vector_store import Point, VectorStore
from rag.schemas import IndexedPackage, Installation, StoreReport, SyncPlan

log = logging.getLogger(__name__)

_NAMESPACE = uuid.UUID("5d3f6a0e-8c52-4a71-b0a4-2f8d3c9e6b17")


class Embedder(Protocol):
    @property
    def identity(self) -> str:
        """Everything that determines the vectors (model, prefixes): same identity, same vectors."""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class Indexer:
    def __init__(
        self,
        *,
        store: VectorStore,
        registry: PackageRegistry,
        embedder: Embedder,
        max_chars: int = 1500,
        batch_size: int = 50,
    ):
        self.store = store
        self.registry = registry
        self.embedder = embedder
        self.max_chars = max_chars
        self.batch_size = batch_size

    @property
    def index_format(self) -> str:
        return f"chunker-{CHUNKER_VERSION}|{self.embedder.identity}|max-chars-{self.max_chars}"

    def plan(self, library: str, manifest: Sequence[Installation]) -> SyncPlan:
        indexed = self.registry.indexed(library)
        installed = {inst.package: inst for inst in manifest}

        removed = sorted(indexed.keys() - installed.keys())
        for package in removed:
            self.store.delete({"library": library, "package": package})
            self.registry.remove(library, package)

        def is_current(inst: Installation) -> bool:
            entry = indexed.get(inst.package)
            return entry is not None and entry.installation == inst and entry.index_format == self.index_format

        send = sorted(inst.package for inst in manifest if not is_current(inst))
        plan = SyncPlan(send=send, removed=removed, unchanged=len(manifest) - len(send), batch_size=self.batch_size)
        log.info(
            "sync plan for %s: %d installed, %d to send, %d unchanged, %d removed",
            library, len(manifest), len(plan.send), plan.unchanged, len(plan.removed),
        )  # fmt: skip
        return plan

    def begin(self, inst: Installation, title: str, description: str) -> StoreReport:
        self.store.delete({"library": inst.library, "package": inst.package, "active": False})
        record = {"package": inst.package, "version": inst.version, "title": title, "description": description}
        return self._store(inst, chunk_description(record, self.max_chars))

    def add_pages(self, inst: Installation, pages: Sequence[dict]) -> StoreReport:
        chunks = []
        for page in pages:
            chunks.extend(chunk_topic(page | {"package": inst.package, "version": inst.version}, self.max_chars))
        return self._store(inst, chunks)

    def commit(self, inst: Installation) -> int:
        package = {"library": inst.library, "package": inst.package}
        generation = self._generation(inst)
        # Activate the new version first, then delete the old one: searches see either version
        # (for a moment both), never neither.
        self.store.set_payload(package | {"generation": generation}, {"active": True})
        self.store.delete(package, unless={"generation": generation})
        chunks = self.store.count(package)
        self.registry.save(IndexedPackage(installation=inst, index_format=self.index_format, chunks=chunks))
        log.info("committed %s/%s %s: %d chunks", inst.library, inst.package, inst.version, chunks)
        return chunks

    def _generation(self, inst: Installation) -> str:
        key = f"{inst.built}|{self.index_format}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _content_hash(self, text: str) -> str:
        return hashlib.sha256(f"{self.embedder.identity}\n{text}".encode()).hexdigest()

    def _store(self, inst: Installation, chunks: list[Chunk]) -> StoreReport:
        started = time.perf_counter()
        chunks = list({c.key: c for c in chunks}.values())  # a repeated topic name keeps one copy
        if not chunks:
            return StoreReport(chunks=0, embedded=0, reused=0, seconds=0.0)

        hashes = {c.key: self._content_hash(c.text) for c in chunks}
        known = {
            p.payload["content_hash"]: p.vector for p in self.store.find({}, "content_hash", list(hashes.values()))
        }
        missing = [c for c in chunks if hashes[c.key] not in known]
        if missing:
            # Embed first: if this fails, nothing of this batch was written.
            vectors = self.embedder.embed_documents([c.text for c in missing])
            self.store.ensure_collection(len(vectors[0]))
            known |= {hashes[c.key]: v for c, v in zip(missing, vectors, strict=True)}

        generation = self._generation(inst)
        extra = {"library": inst.library, "built": inst.built, "generation": generation, "active": False}
        points = [
            Point(
                id=str(uuid.uuid5(_NAMESPACE, f"{inst.library}/{generation}/{c.key}")),
                vector=known[hashes[c.key]],
                payload=c.payload() | extra | {"content_hash": hashes[c.key]},
            )
            for c in chunks
        ]
        self.store.upsert(points)
        report = StoreReport(
            chunks=len(chunks),
            embedded=len(missing),
            reused=len(chunks) - len(missing),
            seconds=time.perf_counter() - started,
        )
        log.debug(
            "%s/%s: stored %d chunks (%d embedded, %d reused) in %.2fs",
            inst.library, inst.package, report.chunks, report.embedded, report.reused, report.seconds,
        )  # fmt: skip
        return report
