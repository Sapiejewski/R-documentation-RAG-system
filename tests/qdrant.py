"""A real Qdrant for tests, started once per test run with testcontainers.

Tests that use it are skipped (not failed) when Docker is not available. The image is the
same as in docker-compose.yml, so tests run against the Qdrant version the project uses.
"""

import atexit
import time
import unittest
import urllib.request
import uuid

from testcontainers.core.container import DockerContainer

IMAGE = "qdrant/qdrant:v1.19.1"

_container: DockerContainer | None = None
_url: str | None = None


def qdrant_url() -> str:
    """URL of the shared test Qdrant; raises unittest.SkipTest without Docker."""
    global _container, _url
    if _url is None:
        try:
            _container = DockerContainer(IMAGE).with_exposed_ports(6333).start()
        except Exception as error:
            raise unittest.SkipTest(f"Docker not available for a test Qdrant: {error}") from error
        atexit.register(_container.stop)
        _url = f"http://{_container.get_container_host_ip()}:{_container.get_exposed_port(6333)}"
        _wait_until_ready(_url)
    return _url


def _wait_until_ready(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(f"{url}/readyz", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError(f"Test Qdrant at {url} did not become ready in {timeout:.0f}s")
        time.sleep(0.2)


def fresh_collection() -> str:
    """A collection name no other test uses, so tests never see each other's points."""
    return f"test_{uuid.uuid4().hex[:12]}"


_shared: str | None = None


def shared_collection(dim: int) -> str:
    """Name of one collection (with its payload indexes) reused by every test that needs it.

    Creating a collection with its indexes takes a few seconds, so it is done once per test
    run; tests empty it in setUp instead (see `empty`).
    """
    global _shared
    if _shared is None:
        from rag.services.qdrant import QdrantPackageRegistry, QdrantStore

        _shared = fresh_collection()
        QdrantStore(qdrant_url(), _shared).ensure_collection(dim)
        QdrantPackageRegistry(qdrant_url(), _shared).indexed("any")  # creates the registry collections
    return _shared


def empty(*collections) -> None:
    """Delete every point of the given QdrantStore / QdrantPackageRegistry, keeping the collections."""
    for collection in collections:
        if collection.exists():
            collection._call("POST", "/points/delete?wait=true", {"filter": {"must": []}})
