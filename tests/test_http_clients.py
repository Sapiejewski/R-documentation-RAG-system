import tempfile
import unittest
from pathlib import Path

from rag.ingestion.indexing import index_package
from rag.retrieval.search import search
from rag.retrieval.vector_store import Point
from rag.services.http import ServiceError
from rag.services.ollama import OllamaEmbedder, OllamaLLM
from rag.services.qdrant import QdrantStore
from tests.fakes import DIM, FakeServices, embed_text
from tests.fixtures import write_extracted


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        self.server = FakeServices().start()
        self.addCleanup(self.server.stop)


class OllamaEmbedderTest(ServerTestCase):
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

    def test_missing_model_gives_a_hint(self):
        self.server.missing_model = True
        with self.assertRaisesRegex(ServiceError, "ollama pull nomic-embed-text"):
            OllamaEmbedder(self.server.url, "nomic-embed-text").embed_query("x")

    def test_unreachable_server_says_to_start_the_stack(self):
        stopped = FakeServices().start()
        url = stopped.url
        stopped.stop()
        with self.assertRaisesRegex(ServiceError, "make up"):
            OllamaEmbedder(url, "m").embed_query("x")


class OllamaLLMTest(ServerTestCase):
    def test_generate_disables_thinking_and_reports_speed(self):
        answer = OllamaLLM(self.server.url, "qwen3:1.7b").generate("What does lm() do?")
        self.assertEqual(answer.text, "Fits a linear model.")
        self.assertEqual(answer.tokens_per_second, 10.0)
        request = self.server.generate_requests[-1]
        self.assertEqual((request["model"], request["stream"], request["think"]), ("qwen3:1.7b", False, False))


class QdrantStoreTest(ServerTestCase):
    def store(self, **kwargs) -> QdrantStore:
        return QdrantStore(self.server.url, "docs", **kwargs)

    @staticmethod
    def point(pid: str, text: str, package: str = "p") -> Point:
        return Point(pid, embed_text(text), {"package": package, "topic": pid, "text": text})

    def test_ensure_collection_creates_it_once(self):
        store = self.store()
        self.assertFalse(store.exists())
        store.ensure_collection(DIM)
        self.assertTrue(store.exists())
        store.ensure_collection(DIM)
        self.assertEqual(self.server.collections["docs"]["size"], DIM)

    def test_vector_size_mismatch_is_explained(self):
        store = self.store()
        store.ensure_collection(DIM)
        with self.assertRaisesRegex(ServiceError, "vector size"):
            store.ensure_collection(DIM * 2)

    def test_upsert_search_count_and_delete(self):
        store = self.store()
        store.ensure_collection(DIM)
        store.upsert([self.point("a", "pad a string", "p"), self.point("b", "trim white space", "q")])
        self.assertEqual(store.count(), 2)
        self.assertEqual(store.count("p"), 1)

        hits = store.search(embed_text("pad string"), 5)
        self.assertEqual(hits[0].id, "a")
        self.assertEqual(hits[0].payload["package"], "p")

        only_q = store.search(embed_text("pad string"), 5, package="q")
        self.assertEqual([h.id for h in only_q], ["b"])

        store.delete_package("p")
        self.assertEqual(store.count(), 1)

    def test_upsert_in_batches(self):
        store = self.store()
        store.ensure_collection(DIM)
        store.upsert([self.point(f"id{i}", f"text {i}") for i in range(150)])
        self.assertEqual(store.count(), 150)

    def test_api_key_is_sent_when_configured(self):
        self.store(api_key="secret").ensure_collection(DIM)
        self.assertEqual(set(self.server.api_keys), {"secret"})
        self.server.api_keys.clear()
        self.store().count()
        self.assertEqual(set(self.server.api_keys), {None})


class EndToEndOverHttpTest(ServerTestCase):
    def test_index_then_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_extracted(Path(tmp))
            embedder = OllamaEmbedder(
                self.server.url, "m", doc_prefix="search_document: ", query_prefix="search_query: "
            )
            store = QdrantStore(self.server.url, "r_docs")
            kwargs = {"data_dir": Path(tmp), "embedder": embedder, "store": store, "log": lambda _: None}
            report = index_package("stringr", **kwargs)
            index_package("stringr", **kwargs)  # idempotent over HTTP too
            self.assertEqual(store.count("stringr"), report.chunks)

        hits = search("remove whitespace from both ends", embedder=embedder, store=store, k=3, package="stringr")
        self.assertEqual(hits[0].payload["topic"], "str_trim")


if __name__ == "__main__":
    unittest.main()
