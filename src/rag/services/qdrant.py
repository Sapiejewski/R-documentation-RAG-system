"""Qdrant vector database over its REST API.

Two collections: `<name>` holds the chunks with their vectors (`QdrantStore`, a `VectorStore`);
`<name>_packages` holds one point per indexed package and no vectors (`QdrantPackageRegistry`).
Keeping both in Qdrant means the record of what is indexed cannot drift from the index itself.
"""

import uuid
from collections.abc import Sequence

from rag.retrieval.vector_store import Hit, Point, Where
from rag.schemas import IndexedPackage, Installation
from rag.services.http import ServiceError, request_json

_BATCH = 64
_NAMESPACE = uuid.UUID("0b7c4e52-3f7d-4d5e-9a61-2c8f0e4b9d13")
# Payload fields we filter on get an index, so filtering stays fast on large collections.
# Only those: each index costs ~0.5 s to create (once per collection) and memory to keep.
_KEYWORD_FIELDS = ("library", "package", "generation", "content_hash", "aliases")


def _conditions(where: Where) -> list[dict]:
    return [{"key": key, "match": {"value": value}} for key, value in where.items()]


def _filter(where: Where | None = None, unless: Where | None = None) -> dict:
    flt: dict = {"must": _conditions(where or {})}
    if unless:
        # A nested filter: exclude points that match *all* conditions of `unless`.
        flt["must_not"] = [{"must": _conditions(unless)}]
    return flt


class _Collection:
    def __init__(self, base_url: str, collection: str, api_key: str = "", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self.headers = {"api-key": api_key} if api_key else {}
        self.timeout = timeout

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}/collections/{self.collection}{path}"
        return request_json(method, url, body, self.headers, self.timeout)

    def exists(self) -> bool:
        return bool(self._call("GET", "/exists")["result"]["exists"])

    def _scroll(self, flt: dict, with_vector: bool = False) -> list[dict]:
        points, offset = [], None
        while True:
            body = {"filter": flt, "limit": 256, "with_payload": True, "with_vector": with_vector}
            if offset is not None:
                body["offset"] = offset
            result = self._call("POST", "/points/scroll", body)["result"]
            points.extend(result["points"])
            offset = result.get("next_page_offset")
            if offset is None:
                return points


class QdrantStore(_Collection):
    """Chunks and their vectors (cosine distance)."""

    def ensure_collection(self, dim: int) -> None:
        if self.exists():
            vectors = self._call("GET", "")["result"]["config"]["params"]["vectors"]
            size = vectors.get("size") if isinstance(vectors, dict) else None
            if size is not None and size != dim:
                raise ServiceError(
                    f"Collection '{self.collection}' has vector size {size} but the embedding model "
                    f"produces {dim}. Use a different QDRANT_COLLECTION, or delete the collection "
                    f"(curl -X DELETE {self.base_url}/collections/{self.collection}) and index again."
                )
            return
        self._call("PUT", "", {"vectors": {"size": dim, "distance": "Cosine"}})
        for name in _KEYWORD_FIELDS:
            self._call("PUT", "/index?wait=true", {"field_name": name, "field_schema": "keyword"})
        self._call("PUT", "/index?wait=true", {"field_name": "active", "field_schema": "bool"})

    def upsert(self, points: Sequence[Point]) -> None:
        for start in range(0, len(points), _BATCH):
            batch = points[start : start + _BATCH]
            body = {"points": [{"id": p.id, "vector": p.vector, "payload": p.payload} for p in batch]}
            self._call("PUT", "/points?wait=true", body)

    def search(self, vector: list[float], limit: int, where: Where) -> list[Hit]:
        if not self.exists():
            return []
        body = {"query": vector, "limit": limit, "with_payload": True, "filter": _filter(where)}
        points = self._call("POST", "/points/query", body)["result"]["points"]
        return [Hit(str(p["id"]), float(p["score"]), p.get("payload") or {}) for p in points]

    def find(self, where: Where, key: str, values: Sequence[str]) -> list[Point]:
        if not values or not self.exists():
            return []
        flt = _filter(where)
        flt["must"].append({"key": key, "match": {"any": list(values)}})
        return [Point(str(p["id"]), p["vector"], p["payload"]) for p in self._scroll(flt, with_vector=True)]

    def set_payload(self, where: Where, values: dict) -> None:
        self._call("POST", "/points/payload?wait=true", {"payload": values, "filter": _filter(where)})

    def delete(self, where: Where, unless: Where | None = None) -> None:
        if self.exists():
            self._call("POST", "/points/delete?wait=true", {"filter": _filter(where, unless)})

    def count(self, where: Where | None = None) -> int:
        if not self.exists():
            return 0
        body = {"exact": True, "filter": _filter(where)}
        return int(self._call("POST", "/points/count", body)["result"]["count"])


class QdrantPackageRegistry(_Collection):
    """One vectorless point per indexed package: which installation it is and how it was indexed."""

    def __init__(self, base_url: str, collection: str, api_key: str = "", timeout: float = 60.0):
        super().__init__(base_url, f"{collection}_packages", api_key, timeout)
        self._ready = False

    def _ensure(self) -> None:
        if self._ready:
            return
        if not self.exists():
            self._call("PUT", "", {"vectors": {}})
            self._call("PUT", "/index?wait=true", {"field_name": "library", "field_schema": "keyword"})
        self._ready = True

    def indexed(self, library: str) -> dict[str, IndexedPackage]:
        self._ensure()
        entries = {}
        for point in self._scroll(_filter({"library": library})):
            p = point["payload"]
            installation = Installation.model_validate({k: p[k] for k in Installation.model_fields})
            entries[p["package"]] = IndexedPackage(
                installation=installation, index_format=p["index_format"], chunks=p["chunks"]
            )
        return entries

    def save(self, entry: IndexedPackage) -> None:
        self._ensure()
        inst = entry.installation
        point_id = str(uuid.uuid5(_NAMESPACE, f"{inst.library}/{inst.package}"))
        payload = inst.model_dump() | {"index_format": entry.index_format, "chunks": entry.chunks}
        self._call("PUT", "/points?wait=true", {"points": [{"id": point_id, "vector": {}, "payload": payload}]})

    def remove(self, library: str, package: str) -> None:
        self._ensure()
        self._call("POST", "/points/delete?wait=true", {"filter": _filter({"library": library, "package": package})})
