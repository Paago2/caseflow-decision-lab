.PHONY: up down logs build restart shell run api demo smoke demo-docker pid-8000 kill-8000 exp exp-001 exp-002 exp-003 exp-007 exp-008 exp-help register test test-local fmt lint check golden golden-update

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

api:
	TRACE_ENABLED=$${TRACE_ENABLED:-true} \
	UNDERWRITE_PERSIST_RESULTS=$${UNDERWRITE_PERSIST_RESULTS:-true} \
	PORT=$${PORT:-8000} \
	uv run uvicorn caseflow.api.app:app --reload --port $$PORT

demo:
	BASE_URL=$${BASE_URL:-http://localhost:$${PORT:-8000}} bash scripts/demo_mortgage_flow.sh

smoke:
	@base_url="$${BASE_URL:-http://localhost:$${PORT:-8000}}"; \
	for path in /health /ready /version; do \
		code="$$(curl -s -o /dev/null -w '%{http_code}' "$$base_url$$path")"; \
		echo "$$path -> $$code"; \
	done

demo-docker:
	docker compose up -d
	BASE_URL=$${BASE_URL:-http://localhost:8000} bash scripts/demo_mortgage_flow.sh

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

exp-002:
	uv run python experiments/exp_002_train_linear_diabetes.py

exp-003:
	uv run python experiments/exp_003_compare_linear_vs_ridge.py

exp-007:
	uv run python experiments/exp_007_ingest_validate_dataset.py

exp-008:
	uv run python experiments/exp_008_train_from_processed_parquet.py

register:
	@if [ -z "$(MODEL_ID)" ]; then \
		echo 'Usage: make register MODEL_ID=<model_id>'; \
		exit 1; \
	fi
	@src="artifacts/models/$(MODEL_ID)/model.json"; \
	if [ ! -f "$$src" ]; then \
		echo "Artifact not found: $$src"; \
		exit 1; \
	fi; \
	mkdir -p "models/registry/$(MODEL_ID)"; \
	cp "$$src" "models/registry/$(MODEL_ID)/model.json"; \
	echo "Registered $(MODEL_ID) to models/registry/$(MODEL_ID)/model.json"

exp-help:
	@echo 'Usage: make exp ARGS="experiments/<script>.py"'
	@echo 'Example: make exp ARGS="experiments/exp_001_linear_score_sanity.py"'
	@echo 'Shortcut: make exp-001'
	@echo 'Train/export example: make exp-002'
	@echo 'Compare/select/export example: make exp-003'
	@echo 'Ingest/validate dataset example: make exp-007'
	@echo 'Train from processed parquet example: make exp-008'
	@echo 'Register artifact: make register MODEL_ID=diabetes_linreg_v1'

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

golden:
	uv run pytest -q tests/test_golden_underwrite.py

golden-update:
	@if [ "$$CI" = "true" ] || [ "$$CI" = "1" ]; then \
		echo "Refusing to run golden-update in CI"; \
		exit 1; \
	fi
	GOLDEN_UPDATE=1 uv run pytest -q tests/test_golden_underwrite.py
