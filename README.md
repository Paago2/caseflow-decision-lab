# caseflow-decision-lab

## Onboarding (Beginner Guide)

### What this repo is

This repository is a small FastAPI service used to practice production-style API patterns, including health/readiness checks, API key auth, request IDs, and version traceability metadata. It includes local Docker workflows and CI checks so you can run and validate the app the same way in development and automation.

### Prereqs

- Git
- Docker Desktop (or Docker Engine)
- uv (optional if using Docker only)

### Quick Start

```bash
cp .env.example .env
make up
make logs
make down
```

### System verification checklist

- **/health (liveness):** `curl http://localhost:8000/health`
  **Explain:** proves server is running.

- **/ready (readiness):** `curl http://localhost:8000/ready`
  **Explain:** proves config contract is satisfied (APP_ENV valid, API_KEY rules).

- **/protected/ping (auth):** curl with `X-API-Key` header
  Missing key example (expect 401):

  ```bash
  curl -i http://localhost:8000/protected/ping
  ```

  Correct key example (expect 200):

  ```bash
  curl -i -H "X-API-Key: dev-preview-key" http://localhost:8000/protected/ping
  ```

- **/version (traceability):** `curl http://localhost:8000/version`
  **Explain:**
  - `app_name`: service name.
  - `app_env`: runtime environment (local/dev/stg/prod).
  - `version`: app semantic version.
  - `git_sha`: source commit used to build/run this instance.
  - `build_time`: UTC build timestamp.

  This matters because it lets you quickly identify exactly what code and build produced a running instance.

- **X-Request-Id (observability):**

  ```bash
  curl -i -H "X-Request-Id: abc" http://localhost:8000/health
  ```

  The response echoes the same `X-Request-Id` header value, which helps trace a single request across logs and systems.

### Common failures and fixes

- **curl can't connect** -> container not running -> run `docker ps` and `make up`.
- **401 Unauthorized** -> missing/wrong `X-API-Key` -> check `.env` `API_KEY`.
- **/ready returns 503** -> config missing/invalid -> check `APP_ENV` and `API_KEY`.

### Developer workflow

- `make test` (container tests)
- `make test-local` (local tests)
- `make check` (fmt + lint + test-local)
- `uv run pre-commit install`

### Experiments workflow

Use experiments for rapid business-logic iteration without polluting production code in `src/caseflow`.

- Run the example experiment:

  ```bash
  make exp-001
  ```

- Run any experiment script:

  ```bash
  make exp ARGS="experiments/<script>.py"
  ```

- Store local outputs in `artifacts/` (these are gitignored).

Promotion checklist for successful experiments:

1. Move stable logic into `src/caseflow/ml/`.
2. Add tests under `tests/`.
3. Ensure `/ready` gates still pass.

## Observability & Hardening

### Prometheus metrics

The service exposes a public metrics endpoint:

```bash
curl -sS http://localhost:8000/metrics
```

You can scrape this endpoint from Prometheus directly. It includes request
counter and latency histogram metrics (for example, `http_requests_total` and
`http_request_duration_seconds_bucket`).

### Optional rate limiting

Rate limiting is disabled by default. To enable it, set:

```bash
export RATE_LIMIT_ENABLED=true
export RATE_LIMIT_RPS=5
export RATE_LIMIT_BURST=10
export RATE_LIMIT_SCOPE=ip
```

The limiter applies only to `/predict` and `/decision`.

### Audit sink selection

Decision events are logged by default. To write events to JSONL instead:

```bash
export AUDIT_SINK=jsonl
export AUDIT_JSONL_PATH=artifacts/events/decision_events.jsonl
```

Each successful `/decision` call appends one JSON object line to the sink.

## Mortgage 001: Deterministic Underwriting Policy

Endpoint:

```bash
POST /mortgage/decision
```

Example payload:

```json
{
  "features": {
    "credit_score": 720,
    "monthly_income": 10000,
    "monthly_debt": 3000,
    "loan_amount": 300000,
    "property_value": 500000,
    "occupancy": "primary"
  }
}
```

Example approve response:

```json
{
  "policy_id": "mortgage_v1",
  "decision": "approve",
  "reasons": ["APPROVE_POLICY_V1"],
  "derived": {"dti": 0.3, "ltv": 0.6},
  "request_id": "..."
}
```

Example review response:

```json
{
  "policy_id": "mortgage_v1",
  "decision": "review",
  "reasons": ["REVIEW_CREDIT_BORDERLINE"],
  "derived": {"dti": 0.3, "ltv": 0.6},
  "request_id": "..."
}
```

Example decline response:

```json
{
  "policy_id": "mortgage_v1",
  "decision": "decline",
  "reasons": ["DECLINE_CREDIT_TOO_LOW"],
  "derived": {"dti": 0.3, "ltv": 0.6},
  "request_id": "..."
}
```

Reason codes identify which underwriting rule triggered review/decline.
Derived metrics (`dti`, `ltv`) are included for transparent debugging.

### Run locally (clean)

If port 8000 is stuck from an old process, clean it up first:

```bash
# Find PID with lsof
sudo lsof -nP -iTCP:8000 -sTCP:LISTEN

# Or find PID with ss
sudo ss -lptn 'sport = :8000'

# Kill PID (replace <PID>)
kill <PID>
```

Set environment variables for local runs:

```bash
export API_KEY="dev-preview-key"
export MODEL_REGISTRY_DIR="models/registry"
export ACTIVE_MODEL_ID="baseline_v1"
```

Start the API:

```bash
make run
```

Convenience targets:

```bash
make pid-8000
make kill-8000
```

### CI behavior

- CI runs on PRs and pushes to main.
- CI uses `uv.lock` to install deps (deterministic).
- CI exports `GIT_SHA` and `BUILD_TIME` for traceability.

## Developer Workflow

The three commands most developers should know are:

- `make up`
- `make test`
- `make check`

Install pre-commit hooks once per clone with `uv run pre-commit install`.

This project is now installed as a package from the `src/` layout (editable in containers), so imports resolve via the installed package and `PYTHONPATH` is no longer required for normal app/test execution.
