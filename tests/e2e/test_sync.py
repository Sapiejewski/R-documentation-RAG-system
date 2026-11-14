"""A user's story, end to end: install a package, sync, sync again, uninstall, sync, delete a
whole library folder, sync -- in both modes of the R client (docs/setup.md):

    host mode    your own R runs src/client/main.R          (skipped if the host R has no httr2)
    Docker mode  the same code in the r-extract container   (needs no R on the host)

Everything is real: the R client reads real installed packages and talks over HTTP to a rag
API container, which embeds with Ollama and stores in Qdrant. To leave the user's index alone,
the test starts its own rag container on a throwaway collection, and points the client at two
throwaway libraries holding copies of small base R packages.

Needs the running stack (`make up`) and base R packages to copy; skipped otherwise.
"""

import os
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from rag.config import Settings
from rag.retrieval.search import search
from rag.services.http import ServiceError, request_json
from rag.services.ollama import OllamaEmbedder
from rag.services.qdrant import QdrantStore

REPO = Path(__file__).resolve().parents[2]
HOST_R_LIBRARY = Path("/usr/lib/R/library")
SYSTEM_PACKAGE, USER_PACKAGE = "compiler", "tcltk"  # small: about 10 and 40 chunks


def run(*command: str, env: dict | None = None) -> str:
    """Run a command in the repo; return its output (R messages go to stderr)."""
    result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, timeout=600, check=False)
    if result.returncode != 0:
        raise AssertionError(f"{' '.join(command)} failed:\n{result.stdout}{result.stderr}")
    return result.stdout + result.stderr


def host_r_has_httr2() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(["Rscript", "-e", "library(httr2)"], capture_output=True, check=False)
    return probe.returncode == 0


class SyncStory:
    """The story; a subclass says how the R client is run (`sync`) and where it sees the libraries."""

    @classmethod
    def setUpClass(cls):
        cls.settings = Settings.from_env()
        try:
            request_json("GET", f"http://localhost:{os.environ.get('RAG_HOST_PORT', '8000')}/health", timeout=3)
        except ServiceError:
            raise unittest.SkipTest("the stack is not running: make up") from None
        if not (HOST_R_LIBRARY / USER_PACKAGE).is_dir():
            raise unittest.SkipTest(f"no base R packages to copy at {HOST_R_LIBRARY}")

        # The test's own API: a throwaway collection, published on a free port of 127.0.0.1.
        cls.collection = f"e2e_{uuid.uuid4().hex[:8]}"
        cls.api = f"rag-{cls.collection}"
        run("docker", "compose", "run", "-d", "--rm", "--no-deps", "--name", cls.api,
            "-p", "127.0.0.1::8000", "-e", f"QDRANT_COLLECTION={cls.collection}", "rag")  # fmt: skip
        cls.addClassCleanup(cls._remove_api_and_collection)
        cls._wait_until_healthy()
        cls.api_port = run("docker", "port", cls.api, "8000").splitlines()[0].rsplit(":", 1)[1]

        # Two throwaway libraries (folders of installed packages).
        cls.libraries = Path(tempfile.mkdtemp(prefix="e2e-libraries-"))
        cls.addClassCleanup(shutil.rmtree, cls.libraries)
        for library, package in (("system", SYSTEM_PACKAGE), ("user", USER_PACKAGE)):
            shutil.copytree(HOST_R_LIBRARY / package, cls.libraries / library / package)

        cls.store = QdrantStore(cls.settings.qdrant_url, cls.collection, cls.settings.qdrant_api_key)

    @classmethod
    def _wait_until_healthy(cls, timeout: float = 60.0) -> None:
        probe = ["docker", "exec", cls.api, "python", "-c",
                 "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]  # fmt: skip
        deadline = time.monotonic() + timeout
        while subprocess.run(probe, capture_output=True, check=False).returncode:
            if time.monotonic() > deadline:
                raise AssertionError(f"{cls.api} did not become healthy in {timeout:.0f}s")
            time.sleep(1)

    @classmethod
    def _remove_api_and_collection(cls) -> None:
        subprocess.run(["docker", "stop", cls.api], capture_output=True, check=False)
        for name in (cls.collection, f"{cls.collection}_packages", f"{cls.collection}_libraries"):
            request_json("DELETE", f"{cls.settings.qdrant_url}/collections/{name}")

    # How the R client sees the two libraries, and how it is run: set by the subclasses.
    system_library: str
    user_library: str

    def sync(self) -> str:
        raise NotImplementedError

    def chunks(self, package: str) -> int:
        return self.store.count({"package": package, "active": True})

    def test_install_sync_resync_uninstall(self):
        # 1. New packages: both are sent, embedded, stored, searchable.
        output = self.sync()
        self.assertIn(f"{self.system_library}: 1 packages | 1 to send, 0 unchanged, 0 removed", output)
        self.assertIn(f"{self.user_library}/{USER_PACKAGE}", output)
        self.assertGreater(self.chunks(SYSTEM_PACKAGE), 0)
        self.assertGreater(self.chunks(USER_PACKAGE), 0)
        embedder = OllamaEmbedder(
            self.settings.ollama_url,
            self.settings.embedding_model,
            doc_prefix=self.settings.doc_prefix,
            query_prefix=self.settings.query_prefix,
        )
        hits = search("create a Tk window widget", embedder=embedder, store=self.store, k=1)
        self.assertEqual(hits[0].payload["package"], USER_PACKAGE)

        # 2. Nothing changed: nothing is sent.
        output = self.sync()
        self.assertIn(f"{self.system_library}: 1 packages | 0 to send, 1 unchanged, 0 removed", output)
        self.assertIn(f"{self.user_library}: 1 packages | 0 to send, 1 unchanged, 0 removed", output)

        # 3. Uninstalled: removed from the index, the other library is untouched.
        shutil.rmtree(self.libraries / "user" / USER_PACKAGE)
        output = self.sync()
        self.assertIn(f"{self.user_library}: 0 packages | 0 to send, 0 unchanged, 1 removed", output)
        self.assertEqual(self.chunks(USER_PACKAGE), 0)
        self.assertGreater(self.chunks(SYSTEM_PACKAGE), 0)

        # 4. A whole library folder is gone (e.g. a deleted renv project): dropped from the index.
        shutil.rmtree(self.libraries / "system")
        output = self.sync()
        self.assertIn(
            f"{self.system_library}: the folder no longer exists; removed from the index (1 packages)", output
        )
        self.assertEqual(self.chunks(SYSTEM_PACKAGE), 0)
        libraries = [
            lib["library"] for lib in request_json("GET", f"http://127.0.0.1:{self.api_port}/libraries")["libraries"]
        ]
        self.assertEqual(libraries, [self.user_library])


class DockerModeTest(SyncStory, unittest.TestCase):
    """`make sync-docker`: the client in the r-extract container. The throwaway libraries are
    mounted for this test only; normally the container sees just its own Docker library."""

    system_library = "/libraries/e2e-system"
    user_library = "/libraries/e2e-user"

    def sync(self) -> str:
        # Mount only folders that exist: Docker would create a missing one, empty, and the
        # library would look present with no packages instead of gone.
        mounts = []
        for folder, target in (("system", self.system_library), ("user", self.user_library)):
            if (self.libraries / folder).is_dir():
                mounts += ["-v", f"{self.libraries / folder}:{target}:ro"]
        return run(
            "docker", "compose", "run", "--rm", "--no-deps", *mounts,
            "-e", f"RDOCS_LIBRARIES={self.system_library}:{self.user_library}",
            "-e", f"RAG_URL=http://{self.api}:8000",
            "r-extract", "sync",
        )  # fmt: skip


@unittest.skipUnless(host_r_has_httr2(), "the host R has no httr2 (make init installs it)")
class HostModeTest(SyncStory, unittest.TestCase):
    """`make sync`: the client in the R on this computer, with the libraries chosen by path."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.system_library = str(cls.libraries.resolve() / "system")
        cls.user_library = str(cls.libraries.resolve() / "user")

    def sync(self) -> str:
        env = os.environ | {
            "RDOCS_LIBRARIES": f"{self.system_library}{os.pathsep}{self.user_library}",
            "RAG_URL": f"http://127.0.0.1:{self.api_port}",
        }
        return run("Rscript", "src/client/main.R", "sync", env=env)


if __name__ == "__main__":
    unittest.main()
