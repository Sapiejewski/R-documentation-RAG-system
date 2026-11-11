"""Test doubles: a deterministic embedder and a fake Ollama HTTP server.

Qdrant is not faked: tests that need it run a real one (tests/qdrant.py).
"""

import json
import math
import re
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIM = 128


def embed_text(text: str) -> list[float]:
    """Hashed bag of words: texts that share words get similar vectors."""
    vector = [0.0] * DIM
    for token in re.findall(r"[a-z]+", text.lower()):
        vector[zlib.crc32(token.encode()) % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


class FakeEmbedder:
    identity = "fake-bag-of-words"

    def __init__(self) -> None:
        self.calls = 0
        self.texts: list[str] = []  # every text embedded so far

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts.extend(texts)
        return [embed_text(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return embed_text(text)


class FailingEmbedder:
    identity = "failing"

    def embed_documents(self, texts):
        raise RuntimeError("embedding service exploded")

    def embed_query(self, text):
        raise RuntimeError("embedding service exploded")


class FakeOllama:
    """A local HTTP server that imitates the parts of Ollama that rag uses (embed, generate,
    list pulled models). With `missing_model`, no model is pulled."""

    # What `ollama list` shows after `make up` with the default models.
    PULLED = ("nomic-embed-text:latest", "qwen3:1.7b")

    def __init__(self, missing_model: bool = False) -> None:
        self.missing_model = missing_model
        self.embed_requests: list[list[str]] = []
        self.generate_requests: list[dict] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> FakeOllama:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def _handler(self):
        services = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output quiet
                pass

            def _send(self, status: int, body: dict) -> None:
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                if self.path == "/api/tags":
                    pulled = [] if services.missing_model else services.PULLED
                    return self._send(200, {"models": [{"name": name} for name in pulled]})
                return self._send(404, {"error": f"unhandled GET {self.path}"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else {}
                if self.path == "/api/embed":
                    if services.missing_model:
                        return self._send(404, {"error": f"model '{body['model']}' not found"})
                    services.embed_requests.append(body["input"])
                    return self._send(200, {"embeddings": [embed_text(t) for t in body["input"]]})
                if self.path == "/api/generate":
                    services.generate_requests.append(body)
                    answer = {"response": " Fits a linear model. ", "eval_count": 5, "eval_duration": 500_000_000}
                    return self._send(200, answer)
                return self._send(404, {"error": f"unhandled POST {self.path}"})

        return Handler
