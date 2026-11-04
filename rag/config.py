"""Settings, read from environment variables and the repo's .env file."""

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load KEY=VALUE lines into os.environ without overriding existing variables."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


@dataclass(frozen=True)
class Settings:
    ollama_url: str
    qdrant_url: str
    qdrant_api_key: str
    embedding_model: str
    collection: str
    data_dir: Path
    doc_prefix: str
    query_prefix: str

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        env = os.environ
        model = env.get("EMBEDDING_MODEL", "nomic-embed-text")
        # nomic-embed-text was trained with task prefixes; other models use none.
        is_nomic = "nomic" in model
        return cls(
            ollama_url=env.get(
                "OLLAMA_URL", f"http://localhost:{env.get('OLLAMA_HOST_PORT', '11434')}"
            ).rstrip("/"),
            qdrant_url=env.get(
                "QDRANT_URL", f"http://localhost:{env.get('QDRANT_HOST_PORT', '6333')}"
            ).rstrip("/"),
            qdrant_api_key=env.get("QDRANT_API_KEY", ""),
            embedding_model=model,
            collection=env.get("QDRANT_COLLECTION", "r_docs"),
            data_dir=Path(env.get("RAG_DATA_DIR", "data")),
            doc_prefix=env.get("EMBEDDING_DOC_PREFIX", "search_document: " if is_nomic else ""),
            query_prefix=env.get("EMBEDDING_QUERY_PREFIX", "search_query: " if is_nomic else ""),
        )
