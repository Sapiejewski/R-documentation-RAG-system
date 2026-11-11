"""The sync protocol (plan -> begin -> add_pages -> commit), on in-memory stores."""

import unittest

from rag.ingestion.indexing import Indexer
from rag.ingestion.registry import MemoryRegistry
from rag.retrieval.search import format_hit, search
from rag.retrieval.vector_store import MemoryStore
from rag.schemas import Installation
from tests.fakes import FailingEmbedder, FakeEmbedder
from tests.fixtures import OVERVIEW, PAGES, STRINGR, sync_package

REINSTALLED = STRINGR.model_copy(update={"built": "R 4.5.1; ; 2025-06-01 12:00:00 UTC; unix"})
UPGRADED = STRINGR.model_copy(update={"version": "1.6.0", "built": "R 4.5.1; ; 2025-07-01 12:00:00 UTC; unix"})


class SyncTestCase(unittest.TestCase):
    def setUp(self):
        self.store, self.registry, self.embedder = MemoryStore(), MemoryRegistry(), FakeEmbedder()
        self.indexer = self.make_indexer()

    def make_indexer(self, **kwargs) -> Indexer:
        return Indexer(store=self.store, registry=self.registry, embedder=self.embedder, **kwargs)

    def versions_found(self, question: str) -> set[str]:
        hits = search(question, embedder=self.embedder, store=self.store, k=20, package="stringr")
        return {h.payload["version"] for h in hits}


class PlanTest(SyncTestCase):
    def test_new_package_is_requested_then_left_alone(self):
        self.assertEqual(self.indexer.plan("user", [STRINGR]).send, ["stringr"])
        sync_package(self.indexer)
        plan = self.indexer.plan("user", [STRINGR])
        self.assertEqual((plan.send, plan.unchanged), ([], 1))

    def test_reinstall_of_the_same_version_is_requested(self):
        sync_package(self.indexer)
        self.assertEqual(self.indexer.plan("user", [REINSTALLED]).send, ["stringr"])

    def test_uninstalled_package_is_removed_from_the_index(self):
        sync_package(self.indexer)
        plan = self.indexer.plan("user", [])
        self.assertEqual(plan.removed, ["stringr"])
        self.assertEqual(self.store.count(), 0)
        self.assertEqual(self.registry.indexed("user"), {})

    def test_changed_index_format_requests_everything_again(self):
        sync_package(self.indexer)
        self.assertEqual(self.make_indexer(max_chars=800).plan("user", [STRINGR]).send, ["stringr"])

    def test_libraries_are_independent(self):
        sync_package(self.indexer)
        in_docker = STRINGR.model_copy(update={"library": "docker"})
        self.assertEqual(self.indexer.plan("docker", [in_docker]).send, ["stringr"])
        self.indexer.plan("docker", [])  # nothing installed there: must not touch "user"
        self.assertEqual(list(self.registry.indexed("user")), ["stringr"])

    def test_plan_tells_the_client_the_batch_size(self):
        self.assertEqual(self.make_indexer(batch_size=7).plan("user", [STRINGR]).batch_size, 7)


class TransferTest(SyncTestCase):
    def test_committed_package_is_searchable(self):
        sync_package(self.indexer)
        cases = {
            "pad a string to a fixed width": "str_pad",
            "remove whitespace from the start and end": "str_trim",
            "does the string contain a pattern": "str_detect",
            "what does stringr do": "stringr-description",
        }
        for question, expected in cases.items():
            hits = search(question, embedder=self.embedder, store=self.store, k=3)
            self.assertEqual(hits[0].payload["topic"], expected, question)

    def test_nothing_is_searchable_before_commit(self):
        self.indexer.begin(STRINGR, OVERVIEW["title"], OVERVIEW["description"])
        self.indexer.add_pages(STRINGR, PAGES)
        self.assertEqual(self.versions_found("pad a string"), set())
        self.indexer.commit(STRINGR)
        self.assertEqual(self.versions_found("pad a string"), {"1.5.1"})

    def test_upgrade_replaces_the_old_version_at_commit(self):
        sync_package(self.indexer)
        self.indexer.begin(UPGRADED, OVERVIEW["title"], OVERVIEW["description"])
        self.indexer.add_pages(UPGRADED, [p | {"version": "1.6.0"} for p in PAGES])
        self.assertEqual(self.versions_found("pad a string"), {"1.5.1"})  # old one until commit
        chunks = self.indexer.commit(UPGRADED)
        self.assertEqual(self.versions_found("pad a string"), {"1.6.0"})
        self.assertEqual(self.store.count(), chunks)  # old generation deleted, nothing inactive left
        self.assertEqual(self.registry.indexed("user")["stringr"].installation, UPGRADED)

    def test_interrupted_transfer_keeps_the_old_version_and_is_retried(self):
        sync_package(self.indexer)
        self.indexer.begin(UPGRADED, OVERVIEW["title"], OVERVIEW["description"])
        self.indexer.add_pages(UPGRADED, PAGES[:1])  # ... and the client disappears
        self.assertEqual(self.versions_found("pad a string"), {"1.5.1"})
        self.assertEqual(self.indexer.plan("user", [UPGRADED]).send, ["stringr"])

        chunks = sync_package(self.indexer, UPGRADED, [p | {"version": "1.6.0"} for p in PAGES])
        self.assertEqual(self.store.count(), chunks)  # leftovers of the attempt are gone

    def test_unchanged_pages_reuse_their_vectors(self):
        sync_package(self.indexer)
        embedded_once = len(self.embedder.texts)
        changed = [PAGES[0] | {"text": PAGES[0]["text"].replace("minimum width", "minimal width")}] + PAGES[1:]

        self.indexer.begin(REINSTALLED, OVERVIEW["title"], OVERVIEW["description"])
        report = self.indexer.add_pages(REINSTALLED, changed)
        self.indexer.commit(REINSTALLED)

        newly_embedded = self.embedder.texts[embedded_once:]
        self.assertTrue(newly_embedded)
        self.assertTrue(all("minimal width" in text for text in newly_embedded))  # only str_pad changed
        self.assertEqual(report.embedded, len(newly_embedded))
        self.assertGreater(report.reused, 0)

    def test_resending_a_batch_is_harmless(self):
        self.indexer.begin(STRINGR, OVERVIEW["title"], OVERVIEW["description"])
        self.indexer.add_pages(STRINGR, PAGES)
        report = self.indexer.add_pages(STRINGR, PAGES)  # e.g. the client retried after a timeout
        self.assertEqual(report.embedded, 0)
        self.assertEqual(self.indexer.commit(STRINGR), sync_package(self.make_indexer()))

    def test_failed_embedding_keeps_the_previous_version(self):
        sync_package(self.indexer)
        before = dict(self.store.points)
        failing = Indexer(store=self.store, registry=self.registry, embedder=FailingEmbedder())
        with self.assertRaises(RuntimeError):
            failing.add_pages(UPGRADED, PAGES)
        self.assertEqual(self.store.points, before)

    def test_other_packages_are_left_alone(self):
        other = Installation(
            library="user", package="other", version="1.0", built="R 4.5.1; ; 2025-01-01 00:00:00 UTC; unix"
        )
        sync_package(self.indexer, other, [p | {"package": "other"} for p in PAGES])
        before = self.store.count({"package": "other"})
        sync_package(self.indexer)
        sync_package(self.indexer, REINSTALLED)
        self.assertEqual(self.store.count({"package": "other"}), before)

    def test_repeated_topic_name_keeps_one_copy(self):
        report = self.indexer.add_pages(STRINGR, [PAGES[0], PAGES[0]])
        self.assertEqual(report.chunks, len({c for c in self.store.points}))

    def test_format_hit_is_readable(self):
        sync_package(self.indexer)
        text = format_hit(1, search("pad a string", embedder=self.embedder, store=self.store, k=1)[0])
        self.assertIn("stringr::str_pad", text)
        self.assertIn("chunk 1/", text)


if __name__ == "__main__":
    unittest.main()
