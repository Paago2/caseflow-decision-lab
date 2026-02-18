# Experiments Workflow

Use this directory for local business-logic experiments that should not directly pollute production code under `src/caseflow`.

## How to run

Run an experiment script with:

```bash
make exp ARGS="experiments/<script>.py"
```

Example:

```bash
make exp-001
```

## Suggested structure

- One script per experiment, with a clear ID prefix (for example: `exp_001_*`, `exp_002_*`).
- Keep scripts self-contained and readable.
- Write outputs to `artifacts/` (never to `src/`).
- Document assumptions and expected inputs at the top of each script.

## Promotion to production

When an experiment is accepted:

1. Move stable logic into `src/caseflow/ml/` (or the correct production module).
2. Add/expand tests under `tests/`.
3. Verify service readiness checks still pass (`/ready` contract unchanged unless explicitly planned).
4. Keep experiment scripts as references or remove them after promotion.
