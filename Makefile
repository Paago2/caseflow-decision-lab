.PHONY: up down logs test

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api

test:
	docker compose run --rm api uv run pytest
