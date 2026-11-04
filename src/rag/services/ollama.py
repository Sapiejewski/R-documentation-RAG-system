"""Local Ollama server: text embeddings (`OllamaEmbedder`) and generation (`OllamaLLM`)."""

from dataclasses import dataclass

from rag.services.http import ServiceError, request_json


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

    @property
    def identity(self) -> str:
        """Everything that determines the vectors: a different model or prefix gives different ones."""
        return f"ollama:{self.model}|{self.doc_prefix}"

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


@dataclass(frozen=True)
class Generation:
    text: str
    tokens: int
    seconds: float  # time spent generating, excluding model load

    @property
    def tokens_per_second(self) -> float:
        return self.tokens / self.seconds if self.seconds else 0.0


class OllamaLLM:
    def __init__(self, base_url: str, model: str, timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> Generation:
        # "think": False stops reasoning models such as Qwen3 from writing a hidden
        # chain of thought first, which is many times slower than the answer itself.
        body = {"model": self.model, "prompt": prompt, "stream": False, "think": False}
        data = request_json("POST", f"{self.base_url}/api/generate", body, timeout=self.timeout)
        if "response" not in data:
            raise ServiceError(f"Ollama returned no text for model '{self.model}'")
        return Generation(
            text=data["response"].strip(),
            tokens=int(data.get("eval_count", 0)),
            seconds=int(data.get("eval_duration", 0)) / 1e9,
        )
