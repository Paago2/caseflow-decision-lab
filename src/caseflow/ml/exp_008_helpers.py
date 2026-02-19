from __future__ import annotations

from typing import Any

REQUIRED_SCHEMA_V2_FEATURES = ("age", "sex", "bmi", "bp")


def select_winner_by_rmse_then_mae(metrics: dict[str, dict[str, float]]) -> str:
    if not metrics:
        raise ValueError("metrics must be non-empty")

    for model_name, scores in metrics.items():
        if "rmse" not in scores or "mae" not in scores:
            raise ValueError(f"metrics for '{model_name}' must include rmse and mae")

    return min(metrics, key=lambda name: (metrics[name]["rmse"], metrics[name]["mae"]))


def build_schema_v2(feature_columns: list[str]) -> dict[str, Any]:
    if not feature_columns:
        raise ValueError("feature_columns must be non-empty")

    missing_required = [
        name for name in REQUIRED_SCHEMA_V2_FEATURES if name not in feature_columns
    ]
    if missing_required:
        raise ValueError(
            "feature_columns missing required schema v2 names: "
            + ", ".join(missing_required)
        )

    features: list[dict[str, Any]] = []
    required_set = set(REQUIRED_SCHEMA_V2_FEATURES)
    for name in feature_columns:
        if name in required_set:
            features.append({"name": name, "dtype": "float", "required": True})
        else:
            features.append(
                {
                    "name": name,
                    "dtype": "float",
                    "required": False,
                    "default": 0.0,
                }
            )

    return {"schema_version": "2", "features": features}
