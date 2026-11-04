"""Data that crosses a boundary: what the R client reports, what the index remembers about a
package, and what a sync answers.

Pydantic models, so the HTTP API validates requests with these very definitions: a malformed
request is rejected with a clear message before any of our code runs. All are immutable
(`frozen`) and reject unknown fields (`extra="forbid"`), so a typo in a client is an error
instead of silently missing data.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

NonEmpty = Annotated[str, Field(min_length=1)]


class Schema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Installation(Schema):
    """One package installed in one R library. `built` (from DESCRIPTION) changes on every
    reinstall, even of the same version, so (version, built) identifies an installation."""

    library: NonEmpty
    package: NonEmpty
    version: NonEmpty
    built: NonEmpty


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
