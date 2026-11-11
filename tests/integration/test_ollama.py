"""The Ollama clients against a fake Ollama HTTP server (Qdrant: see test_qdrant.py)."""

import unittest

from rag.services.http import ServiceError
from rag.services.ollama import OllamaEmbedder, OllamaLLM
from tests.fakes import DIM, FakeOllama


class OllamaTestCase(unittest.TestCase):
    def setUp(self):
        self.server = FakeOllama().start()
        self.addCleanup(self.server.stop)


class OllamaEmbedderTest(OllamaTestCase):
    def test_documents_are_batched_and_prefixed(self):
        embedder = OllamaEmbedder(self.server.url, "m", doc_prefix="search_document: ", batch_size=2)
        vectors = embedder.embed_documents(["a", "b", "c", "d", "e"])
        self.assertEqual(len(vectors), 5)
        self.assertEqual([len(batch) for batch in self.server.embed_requests], [2, 2, 1])
        self.assertEqual(self.server.embed_requests[0][0], "search_document: a")

    def test_query_uses_the_query_prefix(self):
        embedder = OllamaEmbedder(self.server.url, "m", query_prefix="search_query: ")
        self.assertEqual(len(embedder.embed_query("hello")), DIM)
        self.assertEqual(self.server.embed_requests[-1], ["search_query: hello"])

    def test_identity_changes_with_model_and_prefix(self):
        a = OllamaEmbedder(self.server.url, "m", doc_prefix="x: ").identity
        self.assertNotEqual(a, OllamaEmbedder(self.server.url, "other", doc_prefix="x: ").identity)
        self.assertNotEqual(a, OllamaEmbedder(self.server.url, "m", doc_prefix="y: ").identity)

    def test_missing_model_gives_a_hint(self):
        self.server.missing_model = True
        with self.assertRaisesRegex(ServiceError, "ollama pull nomic-embed-text"):
            OllamaEmbedder(self.server.url, "nomic-embed-text").embed_query("x")

    def test_unreachable_server_says_to_start_the_stack(self):
        stopped = FakeOllama().start()
        url = stopped.url
        stopped.stop()
        with self.assertRaisesRegex(ServiceError, "make up"):
            OllamaEmbedder(url, "m").embed_query("x")


class OllamaLLMTest(OllamaTestCase):
    def test_generate_disables_thinking_and_reports_speed(self):
        answer = OllamaLLM(self.server.url, "qwen3:1.7b").generate("What does lm() do?")
        self.assertEqual(answer.text, "Fits a linear model.")
        self.assertEqual(answer.tokens_per_second, 10.0)
        request = self.server.generate_requests[-1]
        self.assertEqual((request["model"], request["stream"], request["think"]), ("qwen3:1.7b", False, False))


if __name__ == "__main__":
    unittest.main()
