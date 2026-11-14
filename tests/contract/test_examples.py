"""The shared example requests (contract/examples/*.json) are what the API accepts.

The R side checks that the client sends requests of the same shape (contract/r/test-api.R);
together the two tests tie the R client to the Python schemas.
"""

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from rag.api.app import create_app
from rag.ingestion.indexing import Indexer
from rag.ingestion.registry import MemoryRegistry
from rag.retrieval.vector_store import MemoryStore
from rag.schemas import BeginRequest, CommitRequest, ForgetRequest, PagesRequest, SyncRequest
from tests.fakes import FakeEmbedder

EXAMPLES = Path(__file__).parent / "examples"

# Protocol order: example file -> (API path, request schema).
ENDPOINTS = {
    "sync": ("/sync", SyncRequest),
    "begin": ("/packages/begin", BeginRequest),
    "pages": ("/packages/pages", PagesRequest),
    "commit": ("/packages/commit", CommitRequest),
    "forget": ("/libraries/forget", ForgetRequest),
}


def example(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


class ExamplesTest(unittest.TestCase):
    def test_there_is_an_example_for_every_endpoint_and_nothing_else(self):
        self.assertEqual({p.stem for p in EXAMPLES.glob("*.json")}, set(ENDPOINTS))

    def test_every_example_is_valid_for_its_schema(self):
        for name, (_, schema) in ENDPOINTS.items():
            with self.subTest(name):
                schema.model_validate(example(name))

    def test_the_api_accepts_the_examples_in_protocol_order(self):
        store = MemoryStore()
        client = TestClient(create_app(Indexer(store=store, registry=MemoryRegistry(), embedder=FakeEmbedder()), "c"))

        for name, (path, _) in ENDPOINTS.items():
            with self.subTest(name):
                response = client.post(path, json=example(name))
                self.assertEqual(response.status_code, 200, response.text)

        self.assertGreater(store.count({"active": True, "package": "compiler"}), 0)


if __name__ == "__main__":
    unittest.main()
