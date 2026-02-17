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
