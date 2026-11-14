"""Data that crosses a boundary: what the R client sends, what the index remembers about a
package, and what the service answers.

Pydantic models, so the HTTP API validates requests with these very definitions: a malformed
request is rejected with a clear message before any of our code runs. All are immutable
(`frozen`) and reject unknown fields (`extra="forbid"`), so a typo in a client is an error
instead of silently missing data.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

NonEmpty = Annotated[str, Field(min_length=1)]
# R's JSON writer (jsonlite) turns a one-element vector into a bare string: accept both.
Strings = Annotated[list[str], BeforeValidator(lambda value: [value] if isinstance(value, str) else value)]

# Upper bound on one request, so a client bug cannot send a whole library in one body.
MAX_PAGES_PER_REQUEST = 500


class Schema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Installation(Schema):
    """One package installed in one R library, as the R client read it. `built` (from DESCRIPTION)
    changes on every reinstall, even of the same version, so (version, built) identifies an
    installation. `extractor` is the version of the client's reading code (EXTRACTOR_VERSION in
    src/client/extract.R): when it changes, the same installation gives different text, so the
    package is sent again."""

    library: NonEmpty
    package: NonEmpty
    version: NonEmpty
    built: NonEmpty
    extractor: int = Field(ge=0)  # 0: indexed before extractor versions existed


class KnownLibrary(Schema):
    """A library the index knows: its folder (absolute path, the library's identity) and which
    client indexed it. `origin` is "host:<computer>" or "docker": a client only judges libraries
    of its own origin -- a host must not drop the Docker library because it lacks that folder."""

    library: NonEmpty
    origin: NonEmpty


class IndexedPackage(Schema):
    """What the index remembers about one package."""

    installation: Installation
    # How it was indexed (chunker version, embedding model, chunk size). If this changes, the
    # package must be indexed again even though the installation itself did not change.
    index_format: str
    chunks: int = Field(ge=0)


class SyncPlan(Schema):
    """The answer to a client's manifest: what to send, what was dropped from the index."""

    send: list[str]
    removed: list[str]
    unchanged: int = Field(ge=0)
    batch_size: int = Field(gt=0)


class StoreReport(Schema):
    """What storing one batch of chunks cost."""

    chunks: int = Field(ge=0)
    embedded: int = Field(ge=0)  # chunks whose vector had to be computed
    reused: int = Field(ge=0)  # chunks whose vector was already in the index
    seconds: float = Field(ge=0)


class CommitReport(Schema):
    """A package switched over to its new version."""

    chunks: int = Field(ge=0)


# --- HTTP requests (rag/api) -------------------------------------------------------------


class InstalledVersion(Schema):
    """One row of the R client's manifest; the library is given once for the whole manifest."""

    package: NonEmpty
    version: NonEmpty
    built: NonEmpty


class SyncRequest(Schema):
    """`POST /sync`: everything installed in one library, which client is asking, and the
    version of its reading code."""

    library: NonEmpty
    origin: NonEmpty
    extractor: int = Field(ge=1)
    packages: list[InstalledVersion]

    def installations(self) -> list[Installation]:
        return [
            Installation(library=self.library, extractor=self.extractor, **row.model_dump()) for row in self.packages
        ]


class BeginRequest(Schema):
    """`POST /packages/begin`: start sending one package, with its overview."""

    installation: Installation
    title: str
    description: str


class HelpPage(Schema):
    """One help page as rendered by R (`tools::Rd2txt`)."""

    name: NonEmpty
    title: str
    aliases: Strings = []
    keywords: Strings = []
    text: str


class PagesRequest(Schema):
    """`POST /packages/pages`: one batch of a package's help pages."""

    installation: Installation
    pages: list[HelpPage] = Field(max_length=MAX_PAGES_PER_REQUEST)


class CommitRequest(Schema):
    """`POST /packages/commit`: everything was sent; switch searches to this version."""

    installation: Installation


class ServiceStatus(Schema):
    """One service the API depends on (Qdrant, Ollama): reachable and ready, or what is wrong."""

    name: str
    ok: bool
    detail: str


class LibraryInfo(Schema):
    """One row of `GET /libraries`."""

    library: str
    origin: str
    packages: int = Field(ge=0)


class Libraries(Schema):
    """`GET /libraries`: every library in the index."""

    libraries: list[LibraryInfo]


class ForgetRequest(Schema):
    """`POST /libraries/forget`: drop a library and all its packages from the index."""

    library: NonEmpty


class ForgetReport(Schema):
    library: str
    removed: list[str]  # its packages that were dropped


class Health(Schema):
    """`GET /health`: the service is up ("ok"), or up but a dependency is not ("degraded");
    how it indexes (a change means a full reindex); the state of each dependency."""

    status: Literal["ok", "degraded"]
    collection: str
    index_format: str
    services: list[ServiceStatus]
