"""Qdrant vector database over its REST API (implements `VectorStore`)."""

from rag.retrieval.vector_store import Hit, Point
from rag.services.http import ServiceError, request_json

_UPSERT_BATCH = 64


class QdrantStore:
    """Minimal Qdrant client using the REST API (cosine distance)."""

    def __init__(self, base_url: str, collection: str, api_key: str = "", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self.headers = {"api-key": api_key} if api_key else {}
        self.timeout = timeout

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}/collections/{self.collection}{path}"
        return request_json(method, url, body, self.headers, self.timeout)

    @staticmethod
    def _package_filter(package: str | None) -> dict | None:
        if package is None:
            return None
        return {"must": [{"key": "package", "match": {"value": package}}]}

    def exists(self) -> bool:
        return bool(self._call("GET", "/exists")["result"]["exists"])

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
        self._call("PUT", "/index?wait=true", {"field_name": "package", "field_schema": "keyword"})

    def delete_package(self, package: str) -> None:
        self._call("POST", "/points/delete?wait=true", {"filter": self._package_filter(package)})

    def upsert(self, points: list[Point]) -> None:
        for start in range(0, len(points), _UPSERT_BATCH):
            batch = points[start : start + _UPSERT_BATCH]
            body = {"points": [{"id": p.id, "vector": p.vector, "payload": p.payload} for p in batch]}
            self._call("PUT", "/points?wait=true", body)

    def search(self, vector: list[float], limit: int, package: str | None = None) -> list[Hit]:
        body: dict = {"query": vector, "limit": limit, "with_payload": True}
        if package is not None:
            body["filter"] = self._package_filter(package)
        points = self._call("POST", "/points/query", body)["result"]["points"]
        return [Hit(str(p["id"]), float(p["score"]), p.get("payload") or {}) for p in points]

    def count(self, package: str | None = None) -> int:
        body: dict = {"exact": True}
        if package is not None:
            body["filter"] = self._package_filter(package)
        return int(self._call("POST", "/points/count", body)["result"]["count"])
