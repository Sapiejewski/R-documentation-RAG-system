"""Text embeddings from a local Ollama server."""

from rag.http import ServiceError, request_json


class OllamaEmbedder:
    def __init__(
        self,
        base_url: str,
        model: str,
        doc_prefix: str = "",
        query_prefix: str = "",
        batch_size: int = 16,
        timeout: float = 300.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.doc_prefix = doc_prefix
        self.query_prefix = query_prefix
        self.batch_size = batch_size
        self.timeout = timeout

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = [self.doc_prefix + text for text in texts[start : start + self.batch_size]]
            vectors.extend(self._embed(batch))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self.query_prefix + text])[0]

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        try:
            data = request_json(
                "POST",
                f"{self.base_url}/api/embed",
                {"model": self.model, "input": inputs},
                timeout=self.timeout,
            )
        except ServiceError as error:
            if "HTTP 404" in str(error):
                raise ServiceError(
                    f"{error}\nModel '{self.model}' may be missing. Try: make up "
                    f"(or: docker compose exec ollama ollama pull {self.model})"
                ) from error
            raise
        embeddings = data.get("embeddings")
        if not embeddings or len(embeddings) != len(inputs):
            raise ServiceError(f"Ollama returned {len(embeddings or [])} embeddings for {len(inputs)} inputs")
        return embeddings
