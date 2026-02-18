.PHONY: up down logs build restart shell run pid-8000 kill-8000 exp exp-001 exp-help test test-local fmt lint check

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

run:
	uv run uvicorn caseflow.api.app:app --reload --port 8000

pid-8000:
	@pid="$$(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true)"; \
	if [ -z "$$pid" ]; then \
		pid="$$(ss -lptn 'sport = :8000' 2>/dev/null | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -n 1)"; \
	fi; \
	if [ -n "$$pid" ]; then \
		echo "$$pid"; \
	else \
		echo "none"; \
	fi

kill-8000:
	@pid="$$(make -s pid-8000)"; \
	if [ "$$pid" = "none" ] || [ -z "$$pid" ]; then \
		echo "No process is listening on port 8000"; \
	else \
		kill "$$pid" && echo "Killed process $$pid on port 8000"; \
	fi

exp:
	@if [ -z "$(ARGS)" ]; then \
		$(MAKE) exp-help; \
		exit 1; \
	fi
	uv run python $(ARGS)

exp-001:
	uv run python experiments/exp_001_linear_score_sanity.py

exp-help:
	@echo 'Usage: make exp ARGS="experiments/<script>.py"'
	@echo 'Example: make exp ARGS="experiments/exp_001_linear_score_sanity.py"'
	@echo 'Shortcut: make exp-001'

# Run tests inside container (closest to production)
test:
	docker compose run --rm api uv run pytest -q

# Run tests locally (fastest feedback loop)
test-local:
	PYTHONPATH=src uv run pytest -q

# Local quality gates
fmt:
	uv run ruff check --fix .
	uv run black .

lint:
	uv run ruff check .

check: fmt lint test-local
