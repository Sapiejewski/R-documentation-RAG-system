"""Measure retrieval quality against a hand-written question set.

A case lists the aliases (function names) of the help pages that answer the
question. A retrieved chunk is relevant if its topic has any of those aliases.
Ranks are positions in the retrieved chunk list (chunks, not distinct topics),
which is what a RAG prompt would actually receive.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from rag.retrieval.vector_store import Hit, VectorStore


@dataclass(frozen=True)
class Case:
    question: str
    expected: tuple[str, ...]


@dataclass(frozen=True)
class CaseResult:
    case: Case
    rank: int | None  # 1-based rank of the first relevant chunk, None if not retrieved
    top_topics: tuple[str, ...]


@dataclass(frozen=True)
class EvalReport:
    results: tuple[CaseResult, ...]

    def hit_at(self, k: int) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.rank is not None and r.rank <= k) / len(self.results)

    @property
    def mrr(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 / r.rank for r in self.results if r.rank is not None) / len(self.results)


def load_cases(path: Path) -> list[Case]:
    if not path.is_file():
        raise FileNotFoundError(f"Question set {path} not found. Pass --cases or create it.")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Case(item["question"], tuple(item["expected"])) for item in raw]


def is_relevant(hit: Hit, expected: tuple[str, ...]) -> bool:
    names = set(hit.payload.get("aliases") or []) | {hit.payload.get("topic")}
    return any(name in names for name in expected)


def rank_of_first_relevant(hits: list[Hit], expected: tuple[str, ...]) -> int | None:
    for rank, hit in enumerate(hits, start=1):
        if is_relevant(hit, expected):
            return rank
    return None


def evaluate(cases: list[Case], *, embedder, store: VectorStore, package: str | None, k: int = 10) -> EvalReport:
    results = []
    for case in cases:
        hits = store.search(embedder.embed_query(case.question), k, package)
        topics = tuple(dict.fromkeys(h.payload.get("topic", "?") for h in hits))[:3]
        results.append(CaseResult(case, rank_of_first_relevant(hits, case.expected), topics))
    return EvalReport(tuple(results))
