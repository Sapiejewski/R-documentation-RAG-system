"""Retrieval: embed a question and fetch the closest chunks of the current package versions."""

from rag.retrieval.vector_store import Hit, VectorStore


def search(query: str, *, embedder, store: VectorStore, k: int = 5, package: str | None = None) -> list[Hit]:
    # Only active points: a package being re-indexed is still searched in its previous version.
    where = {"active": True} | ({"package": package} if package else {})
    return store.search(embedder.embed_query(query), k, where)


def format_hit(rank: int, hit: Hit, preview_chars: int = 220) -> str:
    p = hit.payload
    label = f"{p.get('package', '?')}::{p.get('topic', '?')}"
    where = f"[{p.get('section', '')}] chunk {p.get('chunk_index', 0) + 1}/{p.get('chunk_count', 1)}"
    body = p.get("text", "").split("\n\n", 1)[-1]
    preview = " ".join(body.split())[:preview_chars]
    return f"{rank:>2}. {hit.score:.3f}  {label}  {where}\n      {preview}"
