"""QdrantStore, QdrantPackageRegistry and the whole sync against a real Qdrant (testcontainers).

The same scenarios as test_indexing.py pass on MemoryStore; here they prove that the Qdrant
filters (nested must_not, match any, payload updates, vectorless collection) do the same thing.
"""

import contextlib
import io
import os
import unittest
from unittest import mock

from rag.cli import main
from rag.ingestion.indexing import Indexer
from rag.retrieval.search import search
from rag.retrieval.vector_store import Point
from rag.schemas import IndexedPackage
from rag.services.http import ServiceError
from rag.services.qdrant import QdrantPackageRegistry, QdrantStore
from tests.fakes import DIM, FakeEmbedder, FakeOllama, embed_text
from tests.fixtures import OVERVIEW, PAGES, STRINGR, sync_package
from tests.qdrant import empty, fresh_collection, qdrant_url, shared_collection


class QdrantTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = qdrant_url()
        cls.collection = shared_collection(DIM)
        cls.store = QdrantStore(cls.url, cls.collection)
        cls.registry = QdrantPackageRegistry(cls.url, cls.collection)

    def setUp(self):
        empty(self.store, self.registry)


class QdrantStoreTest(QdrantTestCase):
    @staticmethod
    def point(pid: int, text: str, **payload) -> Point:
        return Point(f"00000000-0000-0000-0000-{pid:012d}", embed_text(text), {"text": text} | payload)

    def test_store_answers_before_its_collection_exists(self):
        store = QdrantStore(self.url, fresh_collection())
        self.assertEqual(store.count(), 0)
        self.assertEqual(store.search(embed_text("x"), 5, {}), [])
        self.assertEqual(store.find({}, "content_hash", ["h"]), [])
        store.delete({"package": "p"})  # no error

    def test_vector_size_mismatch_is_explained(self):
        with self.assertRaisesRegex(ServiceError, "vector size"):
            self.store.ensure_collection(DIM * 2)

    def test_where_filters_search_and_count(self):
        self.store.upsert([
            self.point(1, "pad a string", package="p", active=True, aliases=["str_pad"]),
            self.point(2, "pad a string too", package="q", active=True, aliases=["x"]),
            self.point(3, "pad a string inactive", package="p", active=False, aliases=["str_pad"]),
        ])  # fmt: skip
        hits = self.store.search(embed_text("pad string"), 5, {"package": "p", "active": True})
        self.assertEqual([h.payload["text"] for h in hits], ["pad a string"])
        self.assertEqual(self.store.count({"aliases": "str_pad"}), 2)  # list field contains value
        self.assertEqual(self.store.count(), 3)

    def test_find_returns_vectors_of_matching_values(self):
        self.store.upsert([self.point(i, f"text {i}", content_hash=f"h{i}") for i in range(300)])  # > 1 scroll page
        found = self.store.find({}, "content_hash", [f"h{i}" for i in range(0, 300, 2)])
        self.assertEqual(len(found), 150)
        self.assertEqual(len(found[0].vector), DIM)

    def test_set_payload_and_delete_unless(self):
        self.store.upsert([self.point(1, "a", package="p", generation="old"),
                           self.point(2, "b", package="p", generation="new")])  # fmt: skip
        self.store.set_payload({"package": "p", "generation": "new"}, {"active": True})
        self.store.delete({"package": "p"}, unless={"generation": "new"})
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(self.store.count({"active": True}), 1)


class QdrantRegistryTest(QdrantTestCase):
    def test_save_list_and_remove(self):
        entry = IndexedPackage(installation=STRINGR, index_format="fmt", chunks=7)
        self.registry.save(entry)
        self.registry.save(entry)  # idempotent: one point per library/package
        self.assertEqual(self.registry.indexed("user"), {"stringr": entry})
        self.assertEqual(self.registry.indexed("system"), {})
        self.registry.remove("user", "stringr")
        self.assertEqual(self.registry.indexed("user"), {})


class SyncOverQdrantTest(QdrantTestCase):
    def test_sync_upgrade_and_remove(self):
        embedder = FakeEmbedder()
        indexer = Indexer(store=self.store, registry=self.registry, embedder=embedder)

        self.assertEqual(indexer.plan("user", [STRINGR]).send, ["stringr"])
        chunks = sync_package(indexer)
        self.assertEqual(indexer.plan("user", [STRINGR]).send, [])
        hits = search("remove whitespace from both ends", embedder=embedder, store=self.store, k=3)
        self.assertEqual(hits[0].payload["topic"], "str_trim")

        upgraded = STRINGR.model_copy(update={"version": "1.6.0", "built": "R 4.5.1; ; 2025-07-01 12:00:00 UTC; unix"})
        indexer.begin(upgraded, OVERVIEW["title"], OVERVIEW["description"])
        report = indexer.add_pages(upgraded, [p | {"version": "1.6.0"} for p in PAGES])
        self.assertEqual(report.embedded, 0)  # same texts: every vector reused from Qdrant
        self.assertEqual(indexer.commit(upgraded), chunks)
        self.assertEqual(self.store.count(), chunks)

        self.assertEqual(indexer.plan("user", []).removed, ["stringr"])
        self.assertEqual(self.store.count(), 0)


class CliOverQdrantTest(QdrantTestCase):
    def setUp(self):
        super().setUp()
        self.ollama = FakeOllama().start()
        self.addCleanup(self.ollama.stop)
        env = {"QDRANT_URL": self.url, "QDRANT_COLLECTION": self.collection, "OLLAMA_URL": self.ollama.url}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(list(argv))
        return code, out.getvalue()

    def test_check_reports_every_service(self):
        code, out = self.run_cli("check")
        self.assertEqual(code, 0)
        self.assertIn("Fits a linear model.", out)
        self.assertIn("0 active chunks", out)

    def test_inspect_and_stats_read_the_index(self):
        sync_package(Indexer(store=self.store, registry=self.registry, embedder=FakeEmbedder()))
        code, out = self.run_cli("inspect", "stringr", "str_squish")  # found through its alias
        self.assertEqual(code, 0)
        self.assertIn("stringr::str_trim", out)
        self.assertEqual(self.run_cli("inspect", "stringr", "nope")[0], 1)
        self.assertIn("active chunks", self.run_cli("stats", "--package", "stringr")[1])


if __name__ == "__main__":
    unittest.main()
