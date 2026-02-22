# caseflow-decision-lab

## Badges (fill in repo-specific URLs)

- CI: `[![CI](<CI_BADGE_URL>)](<CI_WORKFLOW_URL>)`
- License: `[![License](<LICENSE_BADGE_URL>)](<LICENSE_FILE_URL>)`
- Python: `[![Python](<PYTHON_BADGE_URL>)](<PYTHON_DOCS_URL>)`

## Project Overview

Caseflow Decision Lab is a deterministic mortgage underwriting sandbox designed
for production-style API and MLOps patterns.

- FastAPI backend with strict request/error envelopes and request ID tracing.
- Document OCR/provenance ingestion feeding retrieval-ready evidence indexing.
- Deterministic underwrite graph with provider seams, trace capture, and replay.
- Golden regression harness for stable contract and output drift detection.
- Minimal React UI + Docker full-stack path for interview/demo storytelling.

## Architecture

```text
Document Text/Image
   -> OCR + Provenance Storage
   -> Evidence Index (chunk + score)
   -> Underwrite Graph (policy + risk + retrieval)
   -> Justifier Provider (deterministic | stub_llm)
   -> Response (schema_version=v1) + Trace + Replay
```

Flow summary:

1. `/ocr/extract` ingests content and writes provenance/text artifacts.
2. Evidence index endpoints prepare citation-ready retrieval chunks.
3. `/mortgage/{case_id}/underwrite` executes deterministic graph nodes.
4. Justifier provider composes reasons/citations without raw evidence leakage.
5. Trace and replay endpoints support reproducibility and diagnostics.

## Quickstart (local dev)

Backend:

```bash
make api
```

Frontend:

```bash
make ui
```

## 2-minute Demo (local)

In a second terminal (with API running):

```bash
make smoke
make demo
```

## Full-stack Docker Demo

```bash
make fullstack-up
make fullstack-demo
make fullstack-down
```

Open the UI at: `http://localhost:3000`

## Local data stack + raw data ingest (Track A)

Bring up API + local infra (Postgres, Redis, MinIO):

```bash
docker compose up --build
```

Check readiness:

```bash
curl http://localhost:8000/ready
```

Dry-run raw data ingest (no upload):

```bash
uv run python scripts/ingest_raw_to_s3.py --dry-run
```

Upload raw data into MinIO bucket:

```bash
uv run python scripts/ingest_raw_to_s3.py
```

## Regression + Contracts

- Golden regression compare mode:

  ```bash
  make golden
  ```

- Golden update mode (intentional only, not in CI):

  ```bash
  make golden-update
  ```

- Underwrite contract includes `schema_version: "v1"` for stable integrations.

## Configuration toggles

- `UNDERWRITE_ENGINE=graph|legacy`
- `JUSTIFIER_PROVIDER=deterministic|stub_llm`
- `TRACE_ENABLED=true|false`

Example:

```bash
TRACE_ENABLED=true JUSTIFIER_PROVIDER=stub_llm make demo
```

## Repo tour (important folders)

- `src/` — backend API, domain logic, graph, settings, and core infrastructure.
- `tests/` — unit/integration tests + golden harness/fixtures.
- `frontend/` — Vite React TypeScript demo UI.
- `artifacts/` — local runtime outputs (traces, provenance, indexes, etc.).
- `scripts/` — deterministic demo/runbook shell scripts.

## Troubleshooting

- **Port conflicts**: use `make pid-8000` and `make kill-8000`.
- **Frontend proxy issues**: verify `/api` proxy target (`http://localhost:8000`).
- **Node version**: use Node 20 for local and CI parity.
- **Docker frontend build**: run `cd frontend && npm ci && npm run build` first.
- **npm audit guidance**: treat as advisory; prioritize runtime-impacting CVEs and
  avoid blind major upgrades in demo branches.

## Screenshots

Drop screenshots in `docs/screenshots/` (placeholder committed). Suggested
captures:

1. UI input panel before running flow
2. Underwrite result + citations table
3. Trace timeline + replay comparison banner
