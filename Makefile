-include .env
export

.PHONY: up down logs clean docker-check

docker-check:
	@docker info >/dev/null 2>&1 || { echo "Docker is currently not running. Please start Docker."; exit 1; }

up: docker-check
	docker compose up -d --wait qdrant ollama
	docker compose run --rm ollama-init
down: docker-check
	docker compose down
logs: docker-check
	docker compose logs -f $(s)
clean: docker-check
	docker compose down -v
smoke: docker-check
	sh scripts/smoke.sh

