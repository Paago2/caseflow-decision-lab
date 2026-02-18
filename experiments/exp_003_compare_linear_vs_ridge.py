"""Experiment 003: compare LinearRegression vs StandardScaler+Ridge.

This script trains/evaluates two candidates on the sklearn diabetes dataset,
selects the best by RMSE (tie-breaker MAE), exports a runtime-compatible
linear model artifact, and writes a metrics report.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.datasets import load_diabetes
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def _evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    return {"rmse": rmse, "mae": mae}


def main() -> None:
    model_id = "diabetes_best_v1"

    data = load_diabetes()
    X = data.data
    y = data.target
    print(f"[stage] load_data: samples={X.shape[0]} features={X.shape[1]}")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
    )
    print(
        "[stage] split: "
        f"train_samples={X_train.shape[0]} test_samples={X_test.shape[0]}"
    )

    print("[stage] train_model_a: model=LinearRegression")
    model_a = LinearRegression()
    model_a.fit(X_train, y_train)
    pred_a = model_a.predict(X_test)
    metrics_a = _evaluate(y_test, pred_a)

    ridge_alpha = 1.0
    print(
        "[stage] train_model_b: "
        f"model=Pipeline(StandardScaler,Ridge(alpha={ridge_alpha}))"
    )
    model_b = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("ridge", Ridge(alpha=ridge_alpha)),
        ]
    )
    model_b.fit(X_train, y_train)
    pred_b = model_b.predict(X_test)
    metrics_b = _evaluate(y_test, pred_b)

    print(
        f"[stage] eval_model_a: rmse={metrics_a['rmse']:.6f} "
        f"mae={metrics_a['mae']:.6f}"
    )
    print(
        f"[stage] eval_model_b: rmse={metrics_b['rmse']:.6f} "
        f"mae={metrics_b['mae']:.6f}"
    )

    model_scores = {
        "linear_regression": metrics_a,
        "scaled_ridge": metrics_b,
    }
    winner = min(
        model_scores,
        key=lambda name: (model_scores[name]["rmse"], model_scores[name]["mae"]),
    )
    print(f"[stage] select_best: winner={winner}")

    if winner == "linear_regression":
        weights = [float(value) for value in model_a.coef_.tolist()]
        bias = float(model_a.intercept_)
    else:
        scaler: StandardScaler = model_b.named_steps["scaler"]
        ridge: Ridge = model_b.named_steps["ridge"]
        w_scaled = ridge.coef_

        # Convert coefficients from standardized feature space back to original
        # feature space so runtime scoring (which uses raw features) is correct.
        w_original = w_scaled / scaler.scale_
        bias_original = ridge.intercept_ - np.sum(
            (scaler.mean_ / scaler.scale_) * w_scaled
        )

        weights = [float(value) for value in w_original.tolist()]
        bias = float(bias_original)

    export_model = {
        "model_id": model_id,
        "type": "linear",
        "bias": bias,
        "weights": weights,
    }

    model_out_dir = Path("artifacts") / "models" / model_id
    model_out_dir.mkdir(parents=True, exist_ok=True)
    model_out_path = model_out_dir / "model.json"
    model_out_path.write_text(json.dumps(export_model, indent=2), encoding="utf-8")

    report = {
        "experiment": "exp_003_compare_linear_vs_ridge",
        "dataset": "diabetes",
        "winner": winner,
        "models": model_scores,
        "export": {
            "model_id": model_id,
            "path": str(model_out_path),
        },
    }
    report_dir = Path("artifacts") / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "exp_003_metrics.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[stage] export_model: path={model_out_path}")
    print(f"[stage] export_metrics: path={report_path}")


if __name__ == "__main__":
    main()
