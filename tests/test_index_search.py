import tempfile
import unittest
from pathlib import Path

from rag.ingestion.indexing import index_package
from rag.retrieval.search import format_hit, search
from rag.retrieval.vector_store import MemoryStore
from tests.fakes import FailingEmbedder, FakeEmbedder
from tests.fixtures import RECORDS, write_extracted


class IndexAndSearchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = Path(self._tmp.name)
        write_extracted(self.data_dir)
        self.embedder = FakeEmbedder()
        self.store = MemoryStore()

    def index(self, package: str = "stringr"):
        return index_package(
            package, data_dir=self.data_dir, embedder=self.embedder, store=self.store, log=lambda _: None
        )

    def test_report_matches_what_is_stored(self):
        report = self.index()
        self.assertEqual(report.package, "stringr")
        self.assertEqual(report.topics, 4)  # 3 help topics + the package overview
        self.assertEqual(report.chunks, self.store.count("stringr"))
        self.assertGreaterEqual(report.chunks, 4)

    def test_retrieval_finds_the_right_topic(self):
        self.index()
        cases = {
            "pad a string to a fixed width": "str_pad",
            "remove whitespace from the start and end": "str_trim",
            "does the string contain a pattern": "str_detect",
            "what does stringr do": "stringr-description",
        }
        for question, expected in cases.items():
            hits = search(question, embedder=self.embedder, store=self.store, k=3)
            self.assertEqual(hits[0].payload["topic"], expected, question)

    def test_reindexing_is_idempotent(self):
        self.index()
        ids = set(self.store.points)
        self.index()
        self.assertEqual(set(self.store.points), ids)

    def test_reindexing_drops_topics_that_no_longer_exist(self):
        self.index()
        write_extracted(self.data_dir, records=[r for r in RECORDS if r.get("name") != "str_trim"])
        self.index()
        topics = {p.payload["topic"] for p in self.store.points.values()}
        self.assertNotIn("str_trim", topics)
        self.assertIn("str_pad", topics)

    def test_other_packages_are_left_alone(self):
        other = [dict(r, package="other") for r in RECORDS]
        write_extracted(self.data_dir, "other", other)
        self.index("other")
        before = self.store.count("other")
        self.index("stringr")
        self.index("stringr")
        self.assertEqual(self.store.count("other"), before)
        hits = search("pad a string", embedder=self.embedder, store=self.store, k=20, package="other")
        self.assertTrue(hits)
        self.assertTrue(all(h.payload["package"] == "other" for h in hits))

    def test_a_failed_embedding_keeps_the_previous_index(self):
        self.index()
        before = dict(self.store.points)
        with self.assertRaises(RuntimeError):
            index_package(
                "stringr",
                data_dir=self.data_dir,
                embedder=FailingEmbedder(),
                store=self.store,
                log=lambda _: None,
            )
        self.assertEqual(self.store.points, before)

    def test_missing_extraction_explains_what_to_do(self):
        with self.assertRaisesRegex(FileNotFoundError, "make extract PKG=nope"):
            self.index("nope")

    def test_duplicate_topic_names_are_skipped(self):
        write_extracted(self.data_dir, records=RECORDS + [RECORDS[1]])
        self.assertEqual(self.index().duplicate_topics, 1)

    def test_invalid_json_reports_the_line(self):
        path = self.data_dir / "extracted" / "stringr.jsonl"
        path.write_text('{"type": "topic"}\n{broken\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, r"stringr.jsonl:2"):
            self.index()

    def test_format_hit_is_readable(self):
        self.index()
        hit = search("pad a string", embedder=self.embedder, store=self.store, k=1)[0]
        text = format_hit(1, hit)
        self.assertIn("stringr::str_pad", text)
        self.assertIn("chunk 1/", text)


if __name__ == "__main__":
    unittest.main()
