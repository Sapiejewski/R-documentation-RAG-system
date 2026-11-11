"""Service status for GET /health (rag/services/status.py) against a fake Ollama and a real Qdrant."""

import unittest
from dataclasses import replace

from rag.config import Settings
from rag.services.status import ollama_status, qdrant_status
from tests.fakes import DIM, FakeOllama
from tests.qdrant import qdrant_url, shared_collection

UNREACHABLE = "http://127.0.0.1:9"


def settings(**changes) -> Settings:
    base = Settings(
        ollama_url=UNREACHABLE,
        qdrant_url=UNREACHABLE,
        qdrant_api_key="",
        embedding_model="nomic-embed-text",
        llm_model="qwen3:1.7b",
        collection="r_docs",
        doc_prefix="",
        query_prefix="",
        log_level="INFO",
    )
    return replace(base, **changes)


class OllamaStatusTest(unittest.TestCase):
    def serve(self, **options) -> str:
        server = FakeOllama(**options).start()
        self.addCleanup(server.stop)
        return server.url

    def test_models_pulled(self):
        status = ollama_status(settings(ollama_url=self.serve()))
        self.assertTrue(status.ok, status.detail)

    def test_missing_models_are_named_with_a_hint(self):
        status = ollama_status(settings(ollama_url=self.serve(missing_model=True)))
        self.assertFalse(status.ok)
        self.assertIn("nomic-embed-text, qwen3:1.7b", status.detail)
        self.assertIn("make up", status.detail)

    def test_unreachable(self):
        status = ollama_status(settings())
        self.assertFalse(status.ok)
        self.assertIn("Cannot reach", status.detail)


class QdrantStatusTest(unittest.TestCase):
    def test_reachable_collection_reports_its_size(self):
        status = qdrant_status(settings(qdrant_url=qdrant_url(), collection=shared_collection(DIM)))
        self.assertTrue(status.ok, status.detail)
        self.assertIn("active chunks", status.detail)

    def test_missing_collection_is_fine_before_the_first_sync(self):
        status = qdrant_status(settings(qdrant_url=qdrant_url(), collection="never_created"))
        self.assertTrue(status.ok)
        self.assertIn("run a sync", status.detail)

    def test_unreachable(self):
        self.assertFalse(qdrant_status(settings()).ok)


if __name__ == "__main__":
    unittest.main()
