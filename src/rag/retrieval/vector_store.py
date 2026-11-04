"""What a vector store is (`VectorStore`), its data types, and a pure-Python store for tests.

Points are selected with `Where`: equality conditions on payload fields that must all hold,
e.g. {"package": "stringr", "active": True}. For a list field (such as `aliases`) a condition
holds when the list contains the value.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from rag.services.http import ServiceError

type Where = Mapping[str, str | bool]


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
    def upsert(self, points: Sequence[Point]) -> None: ...
    def search(self, vector: list[float], limit: int, where: Where) -> list[Hit]: ...

    def find(self, where: Where, key: str, values: Sequence[str]) -> list[Point]:
        """Points matching `where` whose `key` is one of `values`, with their vectors."""
        ...

    def set_payload(self, where: Where, values: dict) -> None: ...

    def delete(self, where: Where, unless: Where | None = None) -> None:
        """Delete the points matching `where`, except those that also match all of `unless`."""
        ...

    def count(self, where: Where | None = None) -> int: ...


def matches(payload: dict, where: Where) -> bool:
    for key, expected in where.items():
        actual = payload.get(key)
        if isinstance(actual, list):
            if expected not in actual:
                return False
        elif actual != expected:
            return False
    return True


def cosine(a: list[float], b: list[float]) -> float:
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / norm if norm else 0.0


class MemoryStore:
    """Cosine-similarity store held in a dict. For tests and quick experiments."""

    def __init__(self) -> None:
        self.dim: int | None = None
        self.points: dict[str, Point] = {}

    def _select(self, where: Where) -> list[Point]:
        return [p for p in self.points.values() if matches(p.payload, where)]

    def ensure_collection(self, dim: int) -> None:
        if self.dim not in (None, dim):
            raise ServiceError(f"Vector size mismatch: store has {self.dim}, got {dim}")
        self.dim = dim

    def upsert(self, points: Sequence[Point]) -> None:
        for point in points:
            self.points[point.id] = point

    def search(self, vector: list[float], limit: int, where: Where) -> list[Hit]:
        scored = sorted(((cosine(vector, p.vector), p) for p in self._select(where)), key=lambda sp: -sp[0])
        return [Hit(p.id, score, p.payload) for score, p in scored[:limit]]

    def find(self, where: Where, key: str, values: Sequence[str]) -> list[Point]:
        wanted = set(values)

        def has_wanted(payload: dict) -> bool:
            value = payload.get(key)
            return bool(wanted & set(value)) if isinstance(value, list) else value in wanted

        return [p for p in self._select(where) if has_wanted(p.payload)]

    def set_payload(self, where: Where, values: dict) -> None:
        for point in self._select(where):
            self.points[point.id] = Point(point.id, point.vector, point.payload | values)

    def delete(self, where: Where, unless: Where | None = None) -> None:
        for point in self._select(where):
            if not (unless and matches(point.payload, unless)):
                del self.points[point.id]

    def count(self, where: Where | None = None) -> int:
        return len(self._select(where or {}))
