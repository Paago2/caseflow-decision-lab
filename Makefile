.PHONY: up down logs build restart shell run api ui ui-build demo smoke demo-docker fullstack-up fullstack-down fullstack-demo pid-8000 kill-8000 exp exp-001 exp-002 exp-003 exp-007 exp-008 exp-help register test test-local fmt lint check golden golden-update

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

ui:
	cd frontend && npm run dev

ui-build:
	cd frontend && npm run build

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

fullstack-up:
	docker compose up -d --build

fullstack-down:
	docker compose down

fullstack-demo: fullstack-up
	@base_url="$${BASE_URL:-http://localhost:8000}"; \
	for i in 1 2 3 4 5 6 7 8 9 10; do \
		if curl -fsS "$$base_url/health" >/dev/null; then \
			break; \
		fi; \
		sleep 1; \
	done
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



# ============================================================
# Backend plumbing (NO build, NO frontend)
# ============================================================

.PHONY: plumbing-up plumbing-down api-exec

# Bring up ONLY backend plumbing (no build)
plumbing-up:
	docker compose up -d postgres redis minio api

plumbing-down:
	docker compose down

# Exec into the running API container (fast loop)
api-exec:
	docker compose exec api bash


# ============================================================
# MinIO / mc helpers (FIXES: mb not found, empty endpoint/creds)
# ============================================================

.PHONY: minio-health minio-mb-lake minio-ls-lake minio-init

# Compose network name (update if your project name differs)
DOCKER_NET ?= caseflow-decision-lab_default

# Hostname reachable INSIDE docker network (container name is most reliable in WSL)
MINIO_HOST ?= caseflow-decision-lab-minio-1
MINIO_PORT ?= 9000

# Credentials (must match docker-compose.yml)
MINIO_ACCESS_KEY ?= minioadmin
MINIO_SECRET_KEY ?= minioadmin

# Bucket + alias
MINIO_BUCKET ?= lake
MINIO_ALIAS ?= local

# mc uses: MC_HOST_<alias>=http://user:pass@host:port
MINIO_MC_HOST := http://$(MINIO_ACCESS_KEY):$(MINIO_SECRET_KEY)@$(MINIO_HOST):$(MINIO_PORT)

# Run minio/mc inside the compose network with MC_HOST configured
MC_RUN = docker run --rm --network $(DOCKER_NET) \
  -e MC_HOST_$(MINIO_ALIAS)="$(MINIO_MC_HOST)" \
  minio/mc

minio-health:
	docker run --rm --network $(DOCKER_NET) curlimages/curl:8.5.0 \
	  -fsS http://$(MINIO_HOST):$(MINIO_PORT)/minio/health/live >/dev/null && \
	  echo "minio live OK (docker network)"

minio-mb-lake:
	@$(MC_RUN) mb -p $(MINIO_ALIAS)/$(MINIO_BUCKET) || true

minio-ls-lake:
	@$(MC_RUN) ls $(MINIO_ALIAS)/$(MINIO_BUCKET) || true

minio-init: minio-mb-lake minio-ls-lake


# ============================================================
# HMDA one-shot runners (NO rebuild)
# - Uses docker compose exec (fast, no new container)
# - run_id keeps sample vs full separate
# ============================================================

.PHONY: hmda-sample hmda-full hmda-run hmda-ls

HMDA_YEAR ?= 2017
HMDA_BUCKET ?= $(MINIO_BUCKET)
HMDA_LIMIT ?= 200000
HMDA_MODE ?= skip
HMDA_RUN_ID ?= sample
HMDA_BRONZE_CSV ?= data/00_raw/finance_housing/hmda/2017/hmda_2017_nationwide_all-records_labels.csv

hmda-run: minio-init plumbing-up
	@echo "[hmda] year=$(HMDA_YEAR) run_id=$(HMDA_RUN_ID) mode=$(HMDA_MODE) limit=$(HMDA_LIMIT)"
	docker compose exec \
	  -e MINIO_S3_ENDPOINT=$(MINIO_HOST):$(MINIO_PORT) \
	  -e MINIO_ROOT_USER=$(MINIO_ACCESS_KEY) \
	  -e MINIO_ROOT_PASSWORD=$(MINIO_SECRET_KEY) \
	  api uv run python -m caseflow.cli.ingest_hmda \
	    --year $(HMDA_YEAR) \
	    --bucket $(HMDA_BUCKET) \
	    --limit $(HMDA_LIMIT) \
	    --mode $(HMDA_MODE) \
	    --run-id $(HMDA_RUN_ID) \
	    --bronze-csv "$(HMDA_BRONZE_CSV)"

hmda-sample:
	@$(MAKE) hmda-run HMDA_RUN_ID=sample HMDA_LIMIT=200000 HMDA_MODE=skip

hmda-full:
	@$(MAKE) hmda-run HMDA_RUN_ID=full HMDA_LIMIT=0 HMDA_MODE=skip

hmda-ls: minio-init
	@$(MC_RUN) ls --recursive $(MINIO_ALIAS)/$(MINIO_BUCKET)/hmda | head -n 200 || true


# ============================================================
# Fannie one-shot runners (NO rebuild)
# - Uses docker compose exec (fast, no new container)
# ============================================================

.PHONY: fannie-sample fannie-full fannie-run fannie-ls

FANNIE_BUCKET ?= $(MINIO_BUCKET)
FANNIE_LIMIT ?= 200000
FANNIE_RUN_ID ?= sample
FANNIE_DATASET_ID ?= 2025Q1
FANNIE_BRONZE ?= data/00_raw/finance_housing/fannie_mae/loan_performance/fannie_mae_2025Q1.csv

fannie-run: minio-init plumbing-up
	@echo "[fannie] dataset=$(FANNIE_DATASET_ID) run_id=$(FANNIE_RUN_ID) limit=$(FANNIE_LIMIT)"
	docker compose exec \
	  -e MINIO_S3_ENDPOINT=$(MINIO_HOST):$(MINIO_PORT) \
	  -e MINIO_ROOT_USER=$(MINIO_ACCESS_KEY) \
	  -e MINIO_ROOT_PASSWORD=$(MINIO_SECRET_KEY) \
	  api uv run python -m caseflow.cli.ingest_fannie \
	    --bronze "$(FANNIE_BRONZE)" \
	    --bucket $(FANNIE_BUCKET) \
	    --dataset-id $(FANNIE_DATASET_ID) \
	    --run-id $(FANNIE_RUN_ID) \
	    --limit $(FANNIE_LIMIT)

fannie-sample:
	@$(MAKE) fannie-run FANNIE_RUN_ID=sample FANNIE_LIMIT=200000

fannie-full:
	@$(MAKE) fannie-run FANNIE_RUN_ID=full FANNIE_LIMIT=0

fannie-ls: minio-init
	@$(MC_RUN) ls --recursive $(MINIO_ALIAS)/$(MINIO_BUCKET)/fannie | head -n 200 || true


# ============================================================
# Reads ALL matching *.txt via glob (DuckDB read_csv supports globs)
# Produces TWO silver outputs:
#   - loans (record_type=20)
#   - perf  (record_type=50)
# ============================================================
.PHONY: freddie-sample freddie-full freddie-run freddie-ls

FREDDIE_BUCKET ?= lake
FREDDIE_RUN_ID ?= sample

# IMPORTANT:
# Pass a glob (many files)
FREDDIE_BRONZE_GLOB ?= data/00_raw/finance_housing/freddie_mac/crt/2025-12/*.txt

FREDDIE_DATASET_ID ?= 2025-12

# Sample = limit to keep runs fast; Full = 0 => no limit
FREDDIE_LIMIT ?= 200000

freddie-run: minio-init plumbing-up
	@echo "[freddie] dataset=$(FREDDIE_DATASET_ID) run_id=$(FREDDIE_RUN_ID) limit=$(FREDDIE_LIMIT) bronze=$(FREDDIE_BRONZE_GLOB)"
	docker compose exec \
	  -e MINIO_S3_ENDPOINT=$(MINIO_HOST):$(MINIO_PORT) \
	  -e MINIO_ROOT_USER=$(MINIO_ACCESS_KEY) \
	  -e MINIO_ROOT_PASSWORD=$(MINIO_SECRET_KEY) \
	  api uv run python -m caseflow.cli.ingest_freddie \
	    --bronze "$(FREDDIE_BRONZE_GLOB)" \
	    --bucket $(FREDDIE_BUCKET) \
	    --dataset-id $(FREDDIE_DATASET_ID) \
	    --run-id $(FREDDIE_RUN_ID) \
	    --limit $(FREDDIE_LIMIT)

freddie-sample:
	@$(MAKE) freddie-run FREDDIE_RUN_ID=sample FREDDIE_LIMIT=200000

freddie-full:
	@$(MAKE) freddie-run FREDDIE_RUN_ID=full FREDDIE_LIMIT=0

freddie-ls: minio-init
	@$(MC_RUN) ls --recursive $(MINIO_ALIAS)/$(MINIO_BUCKET)/freddie | head -n 200 || true


# -----------------------------
# FUNSD OCR v1 (local -> MinIO)
# -----------------------------
FUNSD_LIMIT ?= 5
FUNSD_ENGINE ?= noop
FUNSD_BUCKET ?= lake

FUNSD_IMAGES_TRAIN ?= data/00_raw/documents_ocr/funsd/training_data/images/*.png
FUNSD_ANN_TRAIN ?= data/00_raw/documents_ocr/funsd/training_data/annotations
FUNSD_IMAGES_TEST ?= data/00_raw/documents_ocr/funsd/testing_data/images/*.png
FUNSD_ANN_TEST ?= data/00_raw/documents_ocr/funsd/testing_data/annotations

funsd-ocr-train-sample:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_funsd_ocr \
	    --bronze-images "$(FUNSD_IMAGES_TRAIN)" \
	    --bronze-annotations-dir "$(FUNSD_ANN_TRAIN)" \
	    --bucket "$(FUNSD_BUCKET)" \
	    --split training \
	    --run-id "sample" \
	    --limit-docs "$(FUNSD_LIMIT)" \
	    --ocr-engine "$(FUNSD_ENGINE)"

funsd-ocr-train-full:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_funsd_ocr \
	    --bronze-images "$(FUNSD_IMAGES_TRAIN)" \
	    --bronze-annotations-dir "$(FUNSD_ANN_TRAIN)" \
	    --bucket "$(FUNSD_BUCKET)" \
	    --split training \
	    --run-id "full" \
	    --limit-docs 0 \
	    --ocr-engine "$(FUNSD_ENGINE)"

funsd-ocr-test-sample:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_funsd_ocr \
	    --bronze-images "$(FUNSD_IMAGES_TEST)" \
	    --bronze-annotations-dir "$(FUNSD_ANN_TEST)" \
	    --bucket "$(FUNSD_BUCKET)" \
	    --split testing \
	    --run-id "sample" \
	    --limit-docs "$(FUNSD_LIMIT)" \
	    --ocr-engine "$(FUNSD_ENGINE)"

funsd-ocr-test-full:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_funsd_ocr \
	    --bronze-images "$(FUNSD_IMAGES_TEST)" \
	    --bronze-annotations-dir "$(FUNSD_ANN_TEST)" \
	    --bucket "$(FUNSD_BUCKET)" \
	    --split testing \
	    --run-id "full" \
	    --limit-docs 0 \
	    --ocr-engine "$(FUNSD_ENGINE)"

funsd-ocr-ls:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.minio_ls \
	    --bucket "$(FUNSD_BUCKET)" \
	    --prefix "docs/silver_ocr/funsd" \
	    --limit 80

# -----------------------------
# DocVQA source truth v1 (local -> MinIO)
# -----------------------------
DOCVQA_RUN_ID ?= sample
DOCVQA_LIMIT ?= 5
DOCVQA_BUCKET ?= lake
DOCVQA_SPLIT ?= train

DOCVQA_IMAGES ?= data/00_raw/documents_ocr/docvqa/images/*.jpg
DOCVQA_OCR_DIR ?= data/00_raw/documents_ocr/docvqa/ocr
DOCVQA_QAS_DIR ?= data/00_raw/documents_ocr/docvqa/qas

docvqa-truth-sample:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_docvqa_truth \
	    --bronze-images "$(DOCVQA_IMAGES)" \
	    --bronze-ocr-dir "$(DOCVQA_OCR_DIR)" \
	    --bronze-qas-dir "$(DOCVQA_QAS_DIR)" \
	    --bucket "$(DOCVQA_BUCKET)" \
	    --split "$(DOCVQA_SPLIT)" \
	    --run-id "$(DOCVQA_RUN_ID)" \
	    --limit-docs "$(DOCVQA_LIMIT)"

docvqa-truth-full:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_docvqa_truth \
	    --bronze-images "$(DOCVQA_IMAGES)" \
	    --bronze-ocr-dir "$(DOCVQA_OCR_DIR)" \
	    --bronze-qas-dir "$(DOCVQA_QAS_DIR)" \
	    --bucket "$(DOCVQA_BUCKET)" \
	    --split "$(DOCVQA_SPLIT)" \
	    --run-id "full" \
	    --limit-docs 0

docvqa-truth-ls:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.minio_ls \
	    --bucket "$(DOCVQA_BUCKET)" \
	    --prefix "docs/silver_ocr/docvqa" \
	    --limit 80



# -----------------------------
# Census TIGER ingest
# -----------------------------
TIGER_SHP ?= data/00_raw/geo/census_tiger/2025/bg/VA/tl_2025_51_bg.shp

census-bg-ingest:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_census_tiger \
	    --shapefile "$(TIGER_SHP)"



# -----------------------------
# SROIE source truth v1 (local -> MinIO)
# -----------------------------
SROIE_LIMIT ?= 5
SROIE_BUCKET ?= lake

SROIE_TRAIN_IMAGES ?= data/00_raw/sroie_receipts/SROIE2019/train/img/*.jpg
SROIE_TRAIN_BOXES ?= data/00_raw/sroie_receipts/SROIE2019/train/box
SROIE_TRAIN_ENTITIES ?= data/00_raw/sroie_receipts/SROIE2019/train/entities

SROIE_TEST_IMAGES ?= data/00_raw/sroie_receipts/SROIE2019/test/img/*.jpg
SROIE_TEST_BOXES ?= data/00_raw/sroie_receipts/SROIE2019/test/box
SROIE_TEST_ENTITIES ?= data/00_raw/sroie_receipts/SROIE2019/test/entities

sroie-truth-train-sample:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_sroie_truth \
	    --bronze-images "$(SROIE_TRAIN_IMAGES)" \
	    --bronze-boxes-dir "$(SROIE_TRAIN_BOXES)" \
	    --bronze-entities-dir "$(SROIE_TRAIN_ENTITIES)" \
	    --bucket "$(SROIE_BUCKET)" \
	    --split train \
	    --run-id "sample" \
	    --limit-docs "$(SROIE_LIMIT)"

sroie-truth-train-full:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_sroie_truth \
	    --bronze-images "$(SROIE_TRAIN_IMAGES)" \
	    --bronze-boxes-dir "$(SROIE_TRAIN_BOXES)" \
	    --bronze-entities-dir "$(SROIE_TRAIN_ENTITIES)" \
	    --bucket "$(SROIE_BUCKET)" \
	    --split train \
	    --run-id "full" \
	    --limit-docs 0

sroie-truth-test-sample:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_sroie_truth \
	    --bronze-images "$(SROIE_TEST_IMAGES)" \
	    --bronze-boxes-dir "$(SROIE_TEST_BOXES)" \
	    --bronze-entities-dir "$(SROIE_TEST_ENTITIES)" \
	    --bucket "$(SROIE_BUCKET)" \
	    --split test \
	    --run-id "sample" \
	    --limit-docs "$(SROIE_LIMIT)"

sroie-truth-test-full:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_sroie_truth \
	    --bronze-images "$(SROIE_TEST_IMAGES)" \
	    --bronze-boxes-dir "$(SROIE_TEST_BOXES)" \
	    --bronze-entities-dir "$(SROIE_TEST_ENTITIES)" \
	    --bucket "$(SROIE_BUCKET)" \
	    --split test \
	    --run-id "full" \
	    --limit-docs 0


# -----------------------------
# SynthDog source truth v1 (local -> MinIO)
# -----------------------------
SYNTHDOG_RUN_ID ?= sample
SYNTHDOG_LIMIT ?= 25
SYNTHDOG_BUCKET ?= lake

SYNTHDOG_DATA_DIR ?= data/00_raw/synthdog_en/data
SYNTHDOG_DATASET_INFO ?= data/00_raw/synthdog_en/dataset_infos.json

synthdog-truth-sample:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_synthdog_truth \
	    --bronze-data-dir "$(SYNTHDOG_DATA_DIR)" \
	    --bronze-dataset-info "$(SYNTHDOG_DATASET_INFO)" \
	    --bucket "$(SYNTHDOG_BUCKET)" \
	    --run-id "$(SYNTHDOG_RUN_ID)" \
	    --limit-files "$(SYNTHDOG_LIMIT)"

synthdog-truth-full:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_synthdog_truth \
	    --bronze-data-dir "$(SYNTHDOG_DATA_DIR)" \
	    --bronze-dataset-info "$(SYNTHDOG_DATASET_INFO)" \
	    --bucket "$(SYNTHDOG_BUCKET)" \
	    --run-id "full" \
	    --limit-files 0



# -----------------------------
# Lending Club ingest
# -----------------------------
LENDING_CLUB_BRONZE ?= data/00_raw/misc/lending_club.csv
LENDING_CLUB_BUCKET ?= lake
LENDING_CLUB_RUN_ID ?= sample
LENDING_CLUB_LIMIT ?= 10000

lending-club-sample:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_lending_club \
	    --bronze "$(LENDING_CLUB_BRONZE)" \
	    --bucket "$(LENDING_CLUB_BUCKET)" \
	    --run-id "$(LENDING_CLUB_RUN_ID)" \
	    --limit "$(LENDING_CLUB_LIMIT)"

lending-club-full:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_lending_club \
	    --bronze "$(LENDING_CLUB_BRONZE)" \
	    --bucket "$(LENDING_CLUB_BUCKET)" \
	    --run-id "full" \
	    --limit 0


# -----------------------------
# Sanctions / compliance ingest
# -----------------------------
SANCTIONS_BUCKET ?= lake
SANCTIONS_LIMIT ?= 10000

DEBARMENT_BRONZE ?= data/00_raw/compliance_sanctions/opensanctions/debarment.csv
CONSOLIDATED_SDN_BRONZE ?= data/00_raw/compliance_sanctions/us_treasury_sdn/consolidated_sdn.csv
SDN_BRONZE ?= data/00_raw/compliance_sanctions/us_treasury_sdn/sdn.csv

sanctions-debarment-sample:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_sanctions \
	    --bronze "$(DEBARMENT_BRONZE)" \
	    --bucket "$(SANCTIONS_BUCKET)" \
	    --category "opensanctions" \
	    --dataset-name "debarment" \
	    --run-id "sample" \
	    --limit "$(SANCTIONS_LIMIT)"

sanctions-debarment-full:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_sanctions \
	    --bronze "$(DEBARMENT_BRONZE)" \
	    --bucket "$(SANCTIONS_BUCKET)" \
	    --category "opensanctions" \
	    --dataset-name "debarment" \
	    --run-id "full" \
	    --limit 0

sanctions-consolidated-sdn-sample:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_sanctions \
	    --bronze "$(CONSOLIDATED_SDN_BRONZE)" \
	    --bucket "$(SANCTIONS_BUCKET)" \
	    --category "us_treasury_sdn" \
	    --dataset-name "consolidated_sdn" \
	    --run-id "sample" \
	    --limit "$(SANCTIONS_LIMIT)"

sanctions-consolidated-sdn-full:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_sanctions \
	    --bronze "$(CONSOLIDATED_SDN_BRONZE)" \
	    --bucket "$(SANCTIONS_BUCKET)" \
	    --category "us_treasury_sdn" \
	    --dataset-name "consolidated_sdn" \
	    --run-id "full" \
	    --limit 0

sanctions-sdn-sample:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_sanctions \
	    --bronze "$(SDN_BRONZE)" \
	    --bucket "$(SANCTIONS_BUCKET)" \
	    --category "us_treasury_sdn" \
	    --dataset-name "sdn" \
	    --run-id "sample" \
	    --limit "$(SANCTIONS_LIMIT)"

sanctions-sdn-full:
	docker compose run --rm \
	  -e MINIO_S3_ENDPOINT=caseflow-decision-lab-minio-1:9000 \
	  -e MINIO_ROOT_USER=minioadmin \
	  -e MINIO_ROOT_PASSWORD=minioadmin \
	  api uv run python -m caseflow.cli.ingest_sanctions \
	    --bronze "$(SDN_BRONZE)" \
	    --bucket "$(SANCTIONS_BUCKET)" \
	    --category "us_treasury_sdn" \
	    --dataset-name "sdn" \
	    --run-id "full" \
	    --limit 0


sanctions-all-sample: sanctions-debarment-sample sanctions-consolidated-sdn-sample sanctions-sdn-sample

sanctions-all-full: sanctions-debarment-full sanctions-consolidated-sdn-full sanctions-sdn-full
