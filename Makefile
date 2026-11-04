-include .env
export

GPU ?= auto

# Add the NVIDIA overlay when GPU=on, or when GPU=auto and Docker can attach a
# GPU to a throwaway container. Falls back to CPU otherwise.
GPU_FLAGS = $(shell if [ "$(GPU)" = "on" ] || { [ "$(GPU)" = "auto" ] && docker run --rm --gpus all --entrypoint true ollama/ollama:0.33.3 >/dev/null 2>&1; }; then echo "-f docker-compose.gpu.yml"; fi)
COMPOSE = docker compose -f docker-compose.yml $(GPU_FLAGS)

# R package to work on, e.g. `make ingest PKG=dplyr`.
PKG ?= stringr
UV ?= uv

.PHONY: up down logs clean smoke gpu-check docker-check extract index ingest search evaluate test

.env:
	cp .env.example .env

docker-check:
	@docker info >/dev/null 2>&1 || { echo "Cannot talk to Docker. Is the daemon running, and is your user in the 'docker' group? (try: docker ps)"; exit 1; }

up: docker-check .env
	$(COMPOSE) up -d --wait qdrant ollama
	$(COMPOSE) run --rm ollama-init

down: docker-check
	$(COMPOSE) down

logs: docker-check
	$(COMPOSE) logs -f $(s)

clean: docker-check
	$(COMPOSE) down -v

smoke: docker-check
	sh scripts/smoke.sh

# --- documentation ingestion --------------------------------------------------
# Typical flow: make up && make ingest PKG=stringr && make evaluate PKG=stringr

# Extract the help pages of an R package to data/extracted/$(PKG).jsonl (R in Docker).
extract: docker-check
	mkdir -p data/extracted
	docker compose --profile tools run --rm r-extract $(PKG) /work/data/extracted

# Chunk, embed and store the extracted pages in Qdrant (needs `make up` first).
index:
	$(UV) run python -m rag index $(PKG)

ingest: extract index

# Try a query:  make search q="pad a string with zeros"
search:
	$(UV) run python -m rag search "$(q)" -k 5

# Measure retrieval quality on eval/$(PKG).json
evaluate:
	$(UV) run python -m rag evaluate $(PKG)

# Unit tests (no Docker needed).
test:
	$(UV) run python -m unittest discover -s tests

# Expect library=cuda and PROCESSOR "100% GPU" (after a model has been used).
gpu-check: docker-check
	@docker compose logs ollama 2>&1 | grep -E "library=" | tail -3 || true
	@docker compose exec ollama ollama ps
