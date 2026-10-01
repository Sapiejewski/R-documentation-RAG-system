-include .env
export

GPU ?= auto

# Add the NVIDIA overlay when GPU=on, or when GPU=auto and Docker can attach a
# GPU to a throwaway container. Falls back to CPU otherwise.
GPU_FLAGS = $(shell if [ "$(GPU)" = "on" ] || { [ "$(GPU)" = "auto" ] && docker run --rm --gpus all --entrypoint true ollama/ollama:0.33.3 >/dev/null 2>&1; }; then echo "-f docker-compose.gpu.yml"; fi)
COMPOSE = docker compose -f docker-compose.yml $(GPU_FLAGS)

.PHONY: up down logs clean smoke gpu-check docker-check

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

# Expect library=cuda and PROCESSOR "100% GPU" (after a model has been used).
gpu-check: docker-check
	@docker compose logs ollama 2>&1 | grep -E "library=" | tail -3 || true
	@docker compose exec ollama ollama ps