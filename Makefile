# Shortcuts for everyday commands. Each target is one or two plain commands, so
# you can always run them by hand instead. Settings come from .env (see .env.example).
#
# Typical first run:  make up && make sync && make evaluate

PKG ?= stringr

.PHONY: help up up-gpu down check install search evaluate test lint format

help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' Makefile | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

# --- services (Docker) ------------------------------------------------------------
# Both start Qdrant and Ollama, wait until they are healthy, then download the models.
# up-gpu only adds docker-compose.gpu.yml, which gives Ollama the NVIDIA GPU.
up: ## start the services, Ollama on CPU
	docker compose up -d --wait qdrant ollama
	docker compose run --rm ollama-init

up-gpu: ## start the services, Ollama on an NVIDIA GPU
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --wait qdrant ollama
	docker compose run --rm ollama-init

down: ## stop the services (data is kept)
	docker compose down

check: ## one real embedding + generation: does the stack work, how fast
	uv run rag check

# --- documentation ------------------------------------------------------------------
# Indexing happens through `make sync` (R client -> HTTP API), added with the API service.
install: ## experiments: install PKG into the Docker-only R library
	docker compose run --rm r-extract install $(PKG)

search: ## make search q="pad a string with zeros"
	uv run rag search "$(q)"

evaluate: ## retrieval quality on eval/retrieval/PKG.json
	uv run rag evaluate $(PKG)

# --- development -----------------------------------------------------------------
test: ## all tests; the Qdrant ones start a test Qdrant in Docker (skipped without Docker)
	uv run pytest

lint: ## report style and lint problems
	uv run ruff check .
	uv run ruff format --check .

format: ## fix what can be fixed automatically
	uv run ruff format .
	uv run ruff check --fix .
