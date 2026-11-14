"""The HTTP API (rag/api) as the R client sees it: status codes, validation, answers. In-memory stores.

The same conversation against a real Qdrant: integration/test_qdrant.py (ApiOnQdrantTest).
"""

import unittest

from fastapi.testclient import TestClient

from rag.api.app import create_app
from rag.ingestion.indexing import Indexer
from rag.ingestion.registry import MemoryRegistry
from rag.retrieval.search import search
from rag.retrieval.vector_store import MemoryStore
from rag.schemas import MAX_PAGES_PER_REQUEST, ServiceStatus
from rag.services.http import ServiceError
from tests.fakes import FakeEmbedder
from tests.fixtures import PAGES, STRINGR, manifest, send_package


class UnavailableEmbedder(FakeEmbedder):
    def embed_documents(self, texts):
        raise ServiceError("Cannot reach Ollama")


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.embedder = FakeEmbedder()
        self.indexer = Indexer(store=self.store, registry=MemoryRegistry(), embedder=self.embedder, batch_size=2)
        self.client = TestClient(create_app(self.indexer, "r_docs"))

    def test_health_reports_the_index_format(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "collection": "r_docs", "index_format": self.indexer.index_format, "services": []},
        )

    def test_a_dependency_down_is_degraded_with_the_reason(self):
        services = [
            ServiceStatus(name="qdrant", ok=True, detail="collection 'r_docs': 0 active chunks"),
            ServiceStatus(name="ollama", ok=False, detail="models not pulled: nomic-embed-text. Try: make up"),
        ]
        client = TestClient(create_app(self.indexer, "r_docs", lambda: services))

        answer = client.get("/health").json()

        self.assertEqual(answer["status"], "degraded")
        self.assertIn("Try: make up", answer["services"][1]["detail"])

    def test_a_new_package_is_planned_sent_and_searchable(self):
        plan = self.client.post("/sync", json=manifest(STRINGR)).json()
        self.assertEqual(plan, {"send": ["stringr"], "removed": [], "unchanged": 0, "batch_size": 2})

        committed = send_package(self.client)

        self.assertGreater(committed["chunks"], 0)
        hits = search("pad a string with zeros", embedder=self.embedder, store=self.store, k=1)
        self.assertEqual(hits[0].payload["topic"], "str_pad")

    def test_second_sync_sends_nothing(self):
        self.client.post("/sync", json=manifest(STRINGR))
        send_package(self.client)

        plan = self.client.post("/sync", json=manifest(STRINGR)).json()

        self.assertEqual((plan["send"], plan["unchanged"]), ([], 1))

    def test_uninstalled_package_is_removed(self):
        send_package(self.client)

        plan = self.client.post("/sync", json=manifest()).json()

        self.assertEqual(plan["removed"], ["stringr"])
        self.assertEqual(self.store.count(), 0)

    def test_libraries_lists_what_is_indexed_and_forget_drops_it(self):
        send_package(self.client)  # syncs with the fixture's origin, "host:test"

        self.assertEqual(
            self.client.get("/libraries").json(),
            {"libraries": [{"library": "user", "origin": "host:test", "packages": 1}]},
        )
        answer = self.client.post("/libraries/forget", json={"library": "user"}).json()

        self.assertEqual(answer, {"library": "user", "removed": ["stringr"]})
        self.assertEqual(self.client.get("/libraries").json(), {"libraries": []})
        self.assertEqual(self.store.count(), 0)

    def test_pages_report_embedded_and_reused_chunks(self):
        send_package(self.client)
        installation = STRINGR.model_dump()

        # The same pages again (e.g. a retried request): every vector is reused, none embedded.
        report = self.client.post("/packages/pages", json={"installation": installation, "pages": PAGES}).json()

        self.assertEqual(report["embedded"], 0)
        self.assertEqual(report["reused"], report["chunks"])


class ApiValidationTest(unittest.TestCase):
    """A malformed request is refused with 422 and the offending field, before the indexer runs."""

    def setUp(self):
        self.store = MemoryStore()
        indexer = Indexer(store=self.store, registry=MemoryRegistry(), embedder=FakeEmbedder())
        self.client = TestClient(create_app(indexer, "r_docs"))

    def assert_rejected(self, path: str, body: dict, field: str) -> None:
        response = self.client.post(path, json=body)
        self.assertEqual(response.status_code, 422, response.text)
        locations = [error["loc"] for error in response.json()["detail"]]
        self.assertTrue(any(field in loc for loc in locations), locations)
        self.assertEqual(self.store.count(), 0)

    def test_missing_field(self):
        body = manifest(STRINGR)
        del body["packages"][0]["built"]
        self.assert_rejected("/sync", body, "built")

    def test_unknown_field_is_a_typo_not_ignored(self):
        body = {"installation": STRINGR.model_dump(), "pages": [PAGES[0] | {"titel": "typo"}]}
        self.assert_rejected("/packages/pages", body, "titel")

    def test_sync_without_origin(self):
        body = manifest(STRINGR)
        del body["origin"]
        self.assert_rejected("/sync", body, "origin")

    def test_empty_package_name(self):
        body = {"installation": STRINGR.model_dump() | {"package": ""}}
        self.assert_rejected("/packages/commit", body, "package")

    def test_too_many_pages_in_one_request(self):
        body = {"installation": STRINGR.model_dump(), "pages": [PAGES[0]] * (MAX_PAGES_PER_REQUEST + 1)}
        self.assert_rejected("/packages/pages", body, "pages")


class ApiServiceErrorTest(unittest.TestCase):
    def test_unreachable_ollama_is_503_and_nothing_is_stored(self):
        store = MemoryStore()
        indexer = Indexer(store=store, registry=MemoryRegistry(), embedder=UnavailableEmbedder())
        client = TestClient(create_app(indexer, "r_docs"))

        with self.assertLogs("rag.api.app", "ERROR"):
            response = client.post("/packages/pages", json={"installation": STRINGR.model_dump(), "pages": PAGES})

        self.assertEqual(response.status_code, 503)
        self.assertIn("Cannot reach Ollama", response.json()["detail"])
        self.assertEqual(store.count(), 0)


class ApiLoggingTest(unittest.TestCase):
    def setUp(self):
        indexer = Indexer(store=MemoryStore(), registry=MemoryRegistry(), embedder=FakeEmbedder())
        self.client = TestClient(create_app(indexer, "r_docs"))

    def test_each_request_is_logged_with_status_and_time(self):
        with self.assertLogs("rag.api.app", "INFO") as logs:
            self.client.post("/sync", json=manifest(STRINGR))
        self.assertRegex(logs.output[0], r"INFO:rag.api.app:POST /sync -> 200 in \d+\.\d\ds")

    def test_rejected_request_is_a_warning(self):
        with self.assertLogs("rag.api.app", "WARNING") as logs:
            self.client.post("/sync", json={})
        self.assertIn("POST /sync -> 422", logs.output[0])

    def test_health_checks_stay_out_of_info_logs(self):
        with self.assertLogs("rag.api.app", "DEBUG") as logs:
            self.client.get("/health")
        self.assertTrue(all(line.startswith("DEBUG") for line in logs.output), logs.output)


if __name__ == "__main__":
    unittest.main()
