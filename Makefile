.PHONY: up down logs build restart shell test test-local fmt lint check

up:
	docker compose up -d

build:
	docker compose build

restart:
	docker compose up -d --force-recreate

down:
	docker compose down

logs:
	docker compose logs -f api

shell:
	docker compose run --rm api bash

# Run tests inside container (closest to production)
test:
	docker compose run --rm api uv run pytest -q

# Run tests locally (fastest feedback loop)
test-local:
	PYTHONPATH=src uv run pytest -q

fmt:
	uv run ruff --fix .
	uv run black .

lint:
	uv run ruff .

check: fmt lint test-local
