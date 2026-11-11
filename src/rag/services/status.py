"""Are the services the API depends on reachable and ready? Shown by GET /health, so every
client (the R `doctor`, the RStudio addin later, curl) sees the same answer with a hint.

Short timeouts: this runs on every health check, and a slow answer is itself a problem worth reporting.
"""

from rag.config import Settings
from rag.schemas import ServiceStatus
from rag.services.http import ServiceError, request_json
from rag.services.qdrant import QdrantStore

_TIMEOUT = 3.0


def qdrant_status(settings: Settings) -> ServiceStatus:
    store = QdrantStore(settings.qdrant_url, settings.collection, settings.qdrant_api_key, timeout=_TIMEOUT)
    try:
        if not store.exists():
            return ServiceStatus(
                name="qdrant", ok=True, detail=f"collection '{settings.collection}' empty (run a sync)"
            )
        detail = f"collection '{settings.collection}': {store.count({'active': True})} active chunks"
        return ServiceStatus(name="qdrant", ok=True, detail=detail)
    except ServiceError as error:
        return ServiceStatus(name="qdrant", ok=False, detail=str(error))


def ollama_status(settings: Settings) -> ServiceStatus:
    try:
        tags = request_json("GET", f"{settings.ollama_url}/api/tags", timeout=_TIMEOUT)
    except ServiceError as error:
        return ServiceStatus(name="ollama", ok=False, detail=str(error))
    pulled = {model["name"] for model in tags.get("models", [])}
    # Ollama lists "nomic-embed-text" as "nomic-embed-text:latest".
    missing = [
        m for m in (settings.embedding_model, settings.llm_model) if m not in pulled and f"{m}:latest" not in pulled
    ]
    if missing:
        return ServiceStatus(name="ollama", ok=False, detail=f"models not pulled: {', '.join(missing)}. Try: make up")
    return ServiceStatus(name="ollama", ok=True, detail=f"models {settings.embedding_model}, {settings.llm_model}")


def service_status(settings: Settings) -> list[ServiceStatus]:
    return [qdrant_status(settings), ollama_status(settings)]
