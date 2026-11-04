"""Test doubles: a deterministic embedder and fake Ollama + Qdrant HTTP servers."""

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
    def __init__(self) -> None:
        self.calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [embed_text(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return embed_text(text)


class FailingEmbedder:
    def embed_documents(self, texts):
        raise RuntimeError("embedding service exploded")

    def embed_query(self, text):
        raise RuntimeError("embedding service exploded")


class FakeServices:
    """A local HTTP server that imitates the parts of Ollama and Qdrant that rag uses."""

    def __init__(self, missing_model: bool = False) -> None:
        self.missing_model = missing_model
        self.embed_requests: list[list[str]] = []
        self.generate_requests: list[dict] = []
        self.api_keys: list[str | None] = []
        self.collections: dict[str, dict] = {}  # name -> {"size": int, "points": {id: point}}
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> FakeServices:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    @staticmethod
    def _matches(payload: dict, flt: dict | None) -> bool:
        if not flt:
            return True
        return all(payload.get(c["key"]) == c["match"]["value"] for c in flt.get("must", []))

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

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(length)) if length else {}

            def _route(self, method: str) -> None:
                path = self.path.split("?")[0]
                services.api_keys.append(self.headers.get("api-key"))
                if method == "POST" and path == "/api/embed":
                    body = self._body()
                    if services.missing_model:
                        return self._send(404, {"error": f"model '{body['model']}' not found"})
                    services.embed_requests.append(body["input"])
                    return self._send(200, {"embeddings": [embed_text(t) for t in body["input"]]})
                if method == "POST" and path == "/api/generate":
                    services.generate_requests.append(self._body())
                    answer = {"response": " Fits a linear model. ", "eval_count": 5, "eval_duration": 500_000_000}
                    return self._send(200, answer)

                match = re.fullmatch(r"/collections/([^/]+)(/.*)?", path)
                if not match:
                    return self._send(404, {"status": {"error": "not found"}})
                name, rest = match.group(1), match.group(2) or ""
                collection = services.collections.get(name)

                if method == "GET" and rest == "/exists":
                    return self._send(200, {"result": {"exists": collection is not None}, "status": "ok"})
                if method == "GET" and rest == "":
                    if collection is None:
                        return self._send(404, {"status": {"error": "Not found"}})
                    params = {"vectors": {"size": collection["size"], "distance": "Cosine"}}
                    return self._send(200, {"result": {"config": {"params": params}}, "status": "ok"})
                if method == "PUT" and rest == "":
                    services.collections[name] = {"size": self._body()["vectors"]["size"], "points": {}}
                    return self._send(200, {"result": True, "status": "ok"})
                if collection is None:
                    return self._send(404, {"status": {"error": "Not found"}})
                if method == "PUT" and rest == "/index":
                    return self._send(200, {"result": {"status": "completed"}, "status": "ok"})
                body = self._body()
                points = collection["points"]
                if method == "PUT" and rest == "/points":
                    for p in body["points"]:
                        points[p["id"]] = p
                    return self._send(200, {"result": {"status": "completed"}, "status": "ok"})
                if method == "POST" and rest == "/points/delete":
                    for pid in [i for i, p in points.items() if services._matches(p["payload"], body.get("filter"))]:
                        del points[pid]
                    return self._send(200, {"result": {"status": "completed"}, "status": "ok"})
                if method == "POST" and rest == "/points/count":
                    n = sum(1 for p in points.values() if services._matches(p["payload"], body.get("filter")))
                    return self._send(200, {"result": {"count": n}, "status": "ok"})
                if method == "POST" and rest == "/points/query":
                    query = body["query"]
                    scored = [
                        (sum(a * b for a, b in zip(query, p["vector"], strict=True)), p)
                        for p in points.values()
                        if services._matches(p["payload"], body.get("filter"))
                    ]
                    scored.sort(key=lambda sp: -sp[0])
                    result = [{"id": p["id"], "score": s, "payload": p["payload"]} for s, p in scored[: body["limit"]]]
                    return self._send(200, {"result": {"points": result}, "status": "ok"})
                return self._send(404, {"status": {"error": f"unhandled {method} {path}"}})

            def do_GET(self):
                self._route("GET")

            def do_PUT(self):
                self._route("PUT")

            def do_POST(self):
                self._route("POST")

        return Handler
