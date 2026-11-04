"""What a vector store is (`VectorStore`), its data types, and a pure-Python store for tests."""

import math
from dataclasses import dataclass, field
from typing import Protocol

from rag.services.http import ServiceError


@dataclass(frozen=True)
class Point:
    id: str
    vector: list[float]
    payload: dict


@dataclass(frozen=True)
class Hit:
    id: str
    score: float
    payload: dict = field(default_factory=dict)


class VectorStore(Protocol):
    def ensure_collection(self, dim: int) -> None: ...
    def delete_package(self, package: str) -> None: ...
    def upsert(self, points: list[Point]) -> None: ...
    def search(self, vector: list[float], limit: int, package: str | None = None) -> list[Hit]: ...
    def count(self, package: str | None = None) -> int: ...


class MemoryStore:
    """Cosine-similarity store held in a dict. For tests and quick experiments."""

    def __init__(self) -> None:
        self.dim: int | None = None
        self.points: dict[str, Point] = {}

    def ensure_collection(self, dim: int) -> None:
        if self.dim not in (None, dim):
            raise ServiceError(f"Vector size mismatch: store has {self.dim}, got {dim}")
        self.dim = dim

    def delete_package(self, package: str) -> None:
        self.points = {i: p for i, p in self.points.items() if p.payload.get("package") != package}

    def upsert(self, points: list[Point]) -> None:
        for point in points:
            self.points[point.id] = point

    def search(self, vector: list[float], limit: int, package: str | None = None) -> list[Hit]:
        def cosine(a: list[float], b: list[float]) -> float:
            norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
            return sum(x * y for x, y in zip(a, b, strict=True)) / norm if norm else 0.0

        candidates = [p for p in self.points.values() if package in (None, p.payload.get("package"))]
        scored = sorted(((cosine(vector, p.vector), p) for p in candidates), key=lambda sp: -sp[0])
        return [Hit(p.id, score, p.payload) for score, p in scored[:limit]]

    def count(self, package: str | None = None) -> int:
        return sum(1 for p in self.points.values() if package in (None, p.payload.get("package")))
