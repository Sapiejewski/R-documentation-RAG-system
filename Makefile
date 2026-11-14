# Shortcuts for everyday commands on Linux and macOS. Each target is one or two plain
# commands, so you can always run them by hand instead (on Windows there is usually no
# make: docs/setup.md lists the same steps). Settings come from .env (see .env.example).
#
# Typical first run:  make init && make sync && make evaluate

PKG ?= stringr

.PHONY: help init doctor up up-gpu down logs check sync forget sync-docker install search evaluate test test-unit test-r test-e2e lint format

help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' Makefile | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

# --- setup -------------------------------------------------------------------------
# init.sh only finds R (offering to install it); the rest is R code (src/client/setup.R),
# the same on every system. Windows: .\init.ps1 does the same.
init: ## first setup: check R, httr2, Docker; choose R libraries; start the services
	sh init.sh

doctor: ## check everything the project needs, with a hint for each problem
	Rscript src/client/main.R doctor

# --- services (Docker) ------------------------------------------------------------
# Both start Qdrant, Ollama and the rag API (rebuilt if the code changed), wait until they
# are healthy, then download the models. up-gpu only adds docker-compose.gpu.yml, which
# gives Ollama the NVIDIA GPU.
up: ## start the services, Ollama on CPU
	docker compose up -d --wait --build qdrant ollama rag
	docker compose run --rm ollama-init

up-gpu: ## start the services, Ollama on an NVIDIA GPU
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --wait --build qdrant ollama rag
	docker compose run --rm ollama-init

down: ## stop the services (data is kept)
	docker compose down

logs: ## follow the rag API log (one line per request)
	docker compose logs -f rag

check: ## one real embedding + generation: does the stack work, how fast
	uv run rag check

# --- documentation ------------------------------------------------------------------
# sync: your R lists the packages of the libraries chosen in `make init`, the rag API
# answers which ones changed, and only those are sent and indexed.
sync: ## index new and changed packages of your R libraries (chosen in make init)
	Rscript src/client/main.R sync

# A library still on disk but no longer wanted (a gone folder is dropped by sync itself).
forget: ## drop a library from the index: make forget LIB="/path/to/library"
	Rscript src/client/main.R forget "$(LIB)"

# Docker mode: the same R client in a container, on the Docker library only. For running
# without R on this computer, and for a fixed set of package versions (evaluation).
sync-docker: ## index the Docker library (make install) -- no R needed on this computer
	docker compose run --rm r-extract sync

# --no-deps: installing needs only the R container, not the services.
install: ## Docker mode: install PKG into the Docker library (then: make sync-docker)
	docker compose run --rm --no-deps r-extract install $(PKG)

search: ## make search q="pad a string with zeros"
	uv run rag search "$(q)"

evaluate: ## retrieval quality on eval/retrieval/PKG.json
	uv run rag evaluate $(PKG)

# --- development -----------------------------------------------------------------
# Test levels (tests/__init__.py): unit -> integration -> contract -> e2e.
# One level of Python tests by hand: uv run pytest tests/<level>
test: ## unit + integration + contract tests, Python and R (needs Docker)
	uv run pytest
	docker compose run --rm r-test

test-unit: ## only the fast logic tests, no Docker
	uv run pytest tests/unit

test-r: ## only the R client tests (testthat, in the R container)
	docker compose run --rm r-test

test-e2e: ## the whole stack: R -> API -> Ollama -> Qdrant (needs make up; minutes)
	uv run pytest tests/e2e

lint: ## report style and lint problems
	uv run ruff check .
	uv run ruff format --check .

format: ## fix what can be fixed automatically
	uv run ruff format .
	uv run ruff check --fix .
