from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from caseflow.core.settings import get_settings


@dataclass(frozen=True)
class LinearModel:
    model_id: str
    type: str
    bias: float
    weights: list[float]

    def predict(self, features: list[float]) -> float:
        if len(features) != len(self.weights):
            raise ValueError(
                "'features' must contain exactly "
                f"{len(self.weights)} values for model '{self.model_id}'"
            )

        return self.bias + sum(
            weight * feature for weight, feature in zip(self.weights, features)
        )


_active_model: LinearModel | None = None


def _registry_dir() -> Path:
    settings = get_settings()
    return Path(settings.model_registry_dir)


def list_model_ids() -> list[str]:
    root = _registry_dir()
    if not root.exists() or not root.is_dir():
        return []

    model_ids = [
        item.name
        for item in root.iterdir()
        if item.is_dir() and (item / "model.json").is_file()
    ]
    return sorted(model_ids)


def load_model(model_id: str) -> LinearModel:
    model_path = _registry_dir() / model_id / "model.json"

    if not model_path.is_file():
        raise FileNotFoundError(f"Model '{model_id}' was not found in the registry")

    try:
        payload = json.loads(model_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model '{model_id}' has invalid JSON in model.json") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Model '{model_id}' payload must be a JSON object")

    payload_model_id = payload.get("model_id")
    payload_type = payload.get("type")
    payload_bias = payload.get("bias")
    payload_weights = payload.get("weights")

    if payload_model_id != model_id:
        raise ValueError(
            f"Model '{model_id}' has mismatched model_id "
            f"'{payload_model_id}' in model.json"
        )

    if payload_type != "linear":
        raise ValueError(f"Model '{model_id}' must have type 'linear'")

    try:
        bias = float(payload_bias)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Model '{model_id}' has invalid numeric 'bias' value"
        ) from exc

    if not isinstance(payload_weights, list) or not payload_weights:
        raise ValueError(f"Model '{model_id}' must define a non-empty 'weights' list")

    try:
        weights = [float(value) for value in payload_weights]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Model '{model_id}' has non-numeric values in 'weights'"
        ) from exc

    return LinearModel(
        model_id=model_id,
        type=payload_type,
        bias=bias,
        weights=weights,
    )


def set_active_model(model_id: str) -> LinearModel:
    global _active_model

    model = load_model(model_id)
    _active_model = model
    return model


def get_active_model() -> LinearModel:
    if _active_model is None:
        settings = get_settings()
        try:
            return set_active_model(settings.active_model_id)
        except Exception as exc:
            raise RuntimeError("Active model is not loaded") from exc

    return _active_model


def clear_active_model() -> None:
    global _active_model
    _active_model = None
