# R documentation RAG

A local assistant for R programmers. It indexes the documentation of the R packages installed on
your computer, keeps that index in step when you install, update or remove packages, and answers
questions with a local language model, grounded in that documentation (retrieval-augmented
generation, RAG). Everything runs locally; nothing is sent to a cloud service.

Master's thesis project. The research question: does RAG over the documentation of the *installed*
package versions make a local LLM's answers about R more correct?

## How it works

```
your R                                 Docker
  R client (src/client)    HTTP          rag API (Python, FastAPI)
    lists installed packages  ------->     decides what changed, chunks help pages
    sends the help pages asked for         embeds them (Ollama), stores them (Qdrant)
                                           answers questions with the local LLM
```

- **Incremental sync:** only new, reinstalled or changed packages are sent; a chunk whose text was
  already embedded reuses its vector. Measured on CPU (11 packages, 1183 chunks): first sync 5.5 min,
  sync with no changes 2.7 s, re-sending every package with unchanged text 14 s.
- **Versions you actually have:** answers are grounded in the help pages of the installed versions.
- **With and without RAG:** `rag ask --no-rag` asks the same model the same question without the
  documentation, to compare.

## Requirements

| | Needed for | Checked and (with your consent) fixed by `init` |
|---|---|---|
| R ≥ 4.1 | indexing your own libraries | offers to install R (apt, dnf, brew, winget) |
| R package `httr2` | the R client | offers `install.packages("httr2")` |
| Docker with Compose v2, running | the services | hint only |

No R on your computer? Use Docker mode (below). [uv](https://docs.astral.sh/uv/) is needed only for
development (tests, the `rag` CLI); it installs Python 3.14 by itself.

## Quick start

Linux and macOS:

```bash
make init      # checks the requirements, asks which R libraries to index, starts the services
make sync      # indexes new and changed packages of the chosen libraries
make doctor    # if something does not work: what is wrong and what to do
```

Windows (PowerShell, in the project folder; there is usually no `make`):

```powershell
.\init.ps1                                # if scripts are blocked: powershell -ExecutionPolicy Bypass -File init.ps1
Rscript src/client/main.R sync
Rscript src/client/main.R doctor
```

`init` never installs or starts anything without asking. It can be run again, e.g. to change the
chosen libraries (saved in `.env` as `RDOCS_LIBRARIES`).

Without R on your computer (Docker mode: a library inside Docker, from a dated CRAN snapshot):

```bash
make up                         # the services
make install PKG=dplyr          # install a package into the Docker library
make sync-docker                # index the Docker library
```

## Usage

```bash
make search q="pad a string with zeros"                      # the closest help-page chunks
uv run rag ask "What does dplyr's reframe() do?"             # answer from the documentation, with sources
uv run rag ask "What does dplyr's reframe() do?" --no-rag    # the same model without the documentation
make evaluate PKG=stringr                                    # retrieval quality: hit@k, MRR
make forget LIB="/path/to/library"                           # drop a library from the index
make logs                                                    # the API log; endpoints at http://localhost:8000/docs
```

A library whose folder is gone (a deleted renv project, an old R version) is dropped from the index
by the next `sync`. `make help` lists every target; each is one or two plain commands.

## Development

```bash
make test       # unit + integration + contract tests, Python and R (needs Docker)
make test-unit  # only the fast logic tests, no Docker
make test-e2e   # the whole stack: R -> API -> Ollama -> Qdrant (after make up; ~30 s)
make lint       # ruff
make format     # automatic fixes
```

Tests are organised by level in `tests/`: `unit/`, `integration/` (a real Qdrant via
testcontainers), `contract/` (the API between the R client and the service, checked from both
sides against shared example requests) and `e2e/`.

## Layout

```
src/client/     R client: init, doctor, sync (runs in your R, or in Docker mode in a container)
src/rag/        Python service: HTTP API, ingestion (chunking, indexing), retrieval, generation, evaluation
tests/          tests by level, Python and R
eval/           question sets for the evaluation
init.sh, init.ps1   first setup: find R, then hand over to src/client
```
