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

Train/evaluate/export a real model artifact:

```bash
make exp-002
```

Compare two models and export the best:

```bash
make exp-003
```

Train from processed parquet and export schema-v2 model:

```bash
make exp-008
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

## Exp 002 end-to-end workflow

1. Run training/eval/export:

   ```bash
   make exp-002
   ```

   This writes a runtime-compatible artifact at:
   `artifacts/models/diabetes_linreg_v1/model.json`

2. Register the produced model into the runtime registry:

   ```bash
   make register MODEL_ID=diabetes_linreg_v1
   ```

3. Activate the model through the API:

   ```bash
   curl -sS -X POST \
     -H "X-API-Key: ${API_KEY}" \
     http://localhost:8000/models/activate/diabetes_linreg_v1
   ```

4. Test prediction:

   ```bash
   curl -sS -X POST \
     -H "Content-Type: application/json" \
     -d '{"features":[0.1,-1.2,2.3,0.0,0.5,-0.2,0.1,0.3,-0.4,0.2]}' \
     http://localhost:8000/predict
   ```

## Exp 003 compare-and-promote workflow

1. Run model comparison + export:

   ```bash
   make exp-003
   ```

2. View metrics report:

   ```bash
   cat artifacts/reports/exp_003_metrics.json
   ```

3. Register exported winner model:

   ```bash
   make register MODEL_ID=diabetes_best_v1
   ```

4. Activate and test via API:

   ```bash
   curl -sS -X POST \
     -H "X-API-Key: ${API_KEY}" \
     http://localhost:8000/models/activate/diabetes_best_v1

   curl -sS -X POST \
     -H "Content-Type: application/json" \
     -d '{"features":[0.1,-1.2,2.3,0.0,0.5,-0.2,0.1,0.3,-0.4,0.2]}' \
     http://localhost:8000/predict
   ```

## Exp 008 parquet-train-and-decision workflow

1. Ensure processed parquet exists (from Exp 007):

   ```bash
   make exp-007
   ```

2. Train from processed parquet + export schema-v2 artifact:

   ```bash
   make exp-008
   ```

   This writes:
   - `artifacts/models/diabetes_from_parquet_v1/model.json`
   - `artifacts/reports/exp_008_metrics.json`

3. Register model artifact into runtime registry:

   ```bash
   make register MODEL_ID=diabetes_from_parquet_v1
   ```

4. Activate model:

   ```bash
   curl -sS -X POST \
     -H "X-API-Key: ${API_KEY}" \
     http://localhost:8000/models/activate/diabetes_from_parquet_v1
   ```

5. Call decision endpoint with partial dict (schema-v2 optional defaults apply):

   ```bash
   curl -sS -X POST \
     -H "Content-Type: application/json" \
     -d '{"features":{"age":0.1,"sex":-1.2,"bmi":2.3,"bp":0.0}}' \
     http://localhost:8000/decision
   ```
