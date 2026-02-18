"""Experiment 002: train/evaluate/export a linear regression model on diabetes data.

Outputs a runtime-compatible registry artifact:
artifacts/models/<model_id>/model.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.datasets import load_diabetes
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split


def main() -> None:
    model_id = "diabetes_linreg_v1"

    dataset = load_diabetes()
    features = dataset.data
    targets = dataset.target

    print(f"[stage] dataset: samples={features.shape[0]} features={features.shape[1]}")

    X_train, X_test, y_train, y_test = train_test_split(
        features,
        targets,
        test_size=0.2,
        random_state=42,
    )
    print(
        "[stage] split: "
        f"train_samples={X_train.shape[0]} test_samples={X_test.shape[0]}"
    )

    for idx in range(3):
        feature_mean = float(np.mean(X_train[:, idx]))
        feature_std = float(np.std(X_train[:, idx]))
        print(
            f"[stage] feature_stats: feature_index={idx} "
            f"mean={feature_mean:.6f} std={feature_std:.6f}"
        )

    print("[stage] training: method=LinearRegression")
    model = LinearRegression()
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, predictions)))
    mae = float(mean_absolute_error(y_test, predictions))
    print(f"[stage] eval: rmse={rmse:.6f} mae={mae:.6f}")

    artifact = {
        "model_id": model_id,
        "type": "linear",
        "bias": float(model.intercept_),
        "weights": [float(weight) for weight in model.coef_.tolist()],
    }

    output_dir = Path("artifacts") / "models" / model_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "model.json"
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"[stage] export: path={output_path}")


if __name__ == "__main__":
    main()
