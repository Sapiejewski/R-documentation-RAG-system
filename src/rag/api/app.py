"""The HTTP API. Each sync endpoint is one step of `Indexer` (rag/ingestion/indexing.py):

    POST /sync              manifest of one library -> plan: which packages to send, which were dropped
    POST /packages/begin    start sending one package (its overview)
    POST /packages/pages    one batch of its help pages
    POST /packages/commit   all sent: switch searches to the new version
    GET  /health            the service is up; the index format it uses

Interactive documentation with every request and response schema: /docs.

Request bodies are the pydantic models from rag/schemas.py, so FastAPI rejects a malformed
request (422, with the offending field) before our code runs.

Handlers are plain `def`, not `async def`: the indexer blocks on HTTP calls to Ollama and
Qdrant, so FastAPI runs each one in a worker thread. A handler answers only when its work is
stored, which is the backpressure: the client cannot send faster than embeddings are computed,
and needs no job queue or status polling.
"""

import logging
import time
from importlib.metadata import version

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rag.ingestion.indexing import Indexer
from rag.schemas import (
    BeginRequest,
    CommitReport,
    CommitRequest,
    Health,
    PagesRequest,
    StoreReport,
    SyncPlan,
    SyncRequest,
)
from rag.services.http import ServiceError

log = logging.getLogger(__name__)


def create_app(indexer: Indexer, collection: str) -> FastAPI:
    """The app around one indexer. Tests pass one on in-memory stores; `rag serve` one on Qdrant."""
    app = FastAPI(title="R documentation RAG", version=version("r-docs-rag"))

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        # Health checks come every few seconds: only visible with LOG_LEVEL=DEBUG.
        level = logging.DEBUG if request.url.path == "/health" else logging.INFO
        if response.status_code >= 400:
            level = logging.WARNING
        log.log(
            level, "%s %s -> %d in %.2fs",
            request.method, request.url.path, response.status_code, time.perf_counter() - started,
        )  # fmt: skip
        return response

    @app.exception_handler(ServiceError)
    async def service_unavailable(request: Request, error: ServiceError) -> JSONResponse:
        # Ollama or Qdrant is down: the client may retry later; nothing of this request was committed.
        log.error("%s %s failed: %s", request.method, request.url.path, error)
        return JSONResponse(status_code=503, content={"detail": str(error)})

    @app.get("/health")
    def health() -> Health:
        return Health(status="ok", collection=collection, index_format=indexer.index_format)

    @app.post("/sync")
    def sync(request: SyncRequest) -> SyncPlan:
        return indexer.plan(request.library, request.installations())

    @app.post("/packages/begin")
    def begin(request: BeginRequest) -> StoreReport:
        return indexer.begin(request.installation, request.title, request.description)

    @app.post("/packages/pages")
    def pages(request: PagesRequest) -> StoreReport:
        return indexer.add_pages(request.installation, [page.model_dump() for page in request.pages])

    @app.post("/packages/commit")
    def commit(request: CommitRequest) -> CommitReport:
        return CommitReport(chunks=indexer.commit(request.installation))

    return app
