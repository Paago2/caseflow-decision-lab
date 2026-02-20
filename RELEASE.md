# Release Runbook

## Pre-release checklist

Run from repo root:

```bash
make golden
pytest -q
cd frontend && npm ci && npm run build
```

Optional full-stack validation:

```bash
make fullstack-up
make fullstack-demo
make fullstack-down
```

## Update golden fixtures safely

Only update goldens when behavior changes are intentional and reviewed:

```bash
make golden-update
git diff tests/fixtures/golden/expected
make golden
```

Commit expected fixture diffs with clear rationale in the PR description.

## Verify CI before release

1. Open/update PR to `main`.
2. Confirm CI jobs pass:
   - backend: lint + tests + golden
   - frontend: npm ci + build
3. Ensure no flaky reruns are required.

## Cut release tag (example: v0.1.0)

```bash
git checkout main
git pull --ff-only
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

Create a GitHub Release from tag `v0.1.0` and summarize highlights from
`CHANGELOG.md`.
