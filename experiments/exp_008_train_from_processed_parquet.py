"""Experiment 008: train from processed parquet and export schema-v2 artifact.

Loads dataset contract from configs/datasets.yaml, reads
data/processed/<dataset_name>.parquet, trains/evaluates LinearRegression and
StandardScaler+Ridge, selects winner by RMSE (tie-breaker MAE), and exports
runtime-compatible model artifact + metrics report.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from caseflow.ml.datasets_contract import load_dataset_contract
from caseflow.ml.exp_008_helpers import build_schema_v2, select_winner_by_rmse_then_mae


def _evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
    }


def main() -> None:
    config_path = Path("configs") / "datasets.yaml"
    dataset_name = "example_diabetes_csv"
    model_id = "diabetes_from_parquet_v1"

    contract = load_dataset_contract(config_path=config_path, dataset_name=dataset_name)

    parquet_path = Path("data") / "processed" / f"{contract.name}.parquet"
    if not parquet_path.is_file():
        print("[error] processed parquet not found")
        print(f"[hint] expected path: {parquet_path}")
        print("[hint] run data ingestion first: make exp-007")
        raise SystemExit(1)

    dataframe = pd.read_parquet(parquet_path)

    required_columns = contract.feature_columns + [contract.target_column]
    missing_columns = [col for col in required_columns if col not in dataframe.columns]
    if missing_columns:
        print("[error] parquet missing required columns: " + ", ".join(missing_columns))
        raise SystemExit(1)

    X = dataframe[contract.feature_columns].to_numpy(dtype=float)
    y = dataframe[contract.target_column].to_numpy(dtype=float)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
    )

    model_a = LinearRegression()
    model_a.fit(X_train, y_train)
    metrics_a = _evaluate(y_test, model_a.predict(X_test))

    ridge_alpha = 1.0
    model_b = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("ridge", Ridge(alpha=ridge_alpha)),
        ]
    )
    model_b.fit(X_train, y_train)
    metrics_b = _evaluate(y_test, model_b.predict(X_test))

    all_metrics = {
        "linear_regression": metrics_a,
        "scaled_ridge": metrics_b,
    }
    winner = select_winner_by_rmse_then_mae(all_metrics)

    if winner == "linear_regression":
        weights = [float(value) for value in model_a.coef_.tolist()]
        bias = float(model_a.intercept_)
    else:
        scaler: StandardScaler = model_b.named_steps["scaler"]
        ridge: Ridge = model_b.named_steps["ridge"]
        weights_scaled = ridge.coef_
        weights_original = weights_scaled / scaler.scale_
        bias_original = ridge.intercept_ - np.sum(
            (scaler.mean_ / scaler.scale_) * weights_scaled
        )
        weights = [float(value) for value in weights_original.tolist()]
        bias = float(bias_original)

    schema = build_schema_v2(contract.feature_columns)
    model_artifact = {
        "model_id": model_id,
        "type": "linear",
        "bias": bias,
        "weights": weights,
        "schema": schema,
    }

    model_out_dir = Path("artifacts") / "models" / model_id
    model_out_dir.mkdir(parents=True, exist_ok=True)
    model_out_path = model_out_dir / "model.json"
    model_out_path.write_text(json.dumps(model_artifact, indent=2), encoding="utf-8")

    report = {
        "experiment": "exp_008_train_from_processed_parquet",
        "dataset_name": contract.name,
        "dataset_path": str(parquet_path),
        "winner": winner,
        "models": all_metrics,
        "export": {
            "model_id": model_id,
            "path": str(model_out_path),
        },
    }
    report_dir = Path("artifacts") / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "exp_008_metrics.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[stage] train: dataset={contract.name} rows={len(dataframe)}")
    print(
        f"[stage] metrics_linear_regression: rmse={metrics_a['rmse']:.6f} "
        f"mae={metrics_a['mae']:.6f}"
    )
    print(
        f"[stage] metrics_scaled_ridge: rmse={metrics_b['rmse']:.6f} "
        f"mae={metrics_b['mae']:.6f}"
    )
    print(f"[stage] winner={winner}")
    print(f"[stage] export_model={model_out_path}")
    print(f"[stage] export_report={report_path}")


if __name__ == "__main__":
    main()
