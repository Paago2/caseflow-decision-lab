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
    feature_names: list[str] | None = None

    def predict(self, features: list[float]) -> float:
        if len(features) != len(self.weights):
            raise ValueError(
                "'features' must contain exactly "
                f"{len(self.weights)} values for model '{self.model_id}'"
            )

        return self.bias + sum(
            weight * feature for weight, feature in zip(self.weights, features)
        )

    def vector_from_named_features(self, features: dict[str, object]) -> list[float]:
        if self.feature_names is None:
            raise ValueError(
                "'features' object is not supported for model without schema"
            )

        expected_names = set(self.feature_names)
        provided_names = set(features.keys())

        missing_names = sorted(expected_names - provided_names)
        extra_names = sorted(provided_names - expected_names)

        if missing_names:
            raise ValueError(
                "Missing required feature keys: " + ", ".join(missing_names)
            )

        if extra_names:
            raise ValueError("Unknown feature keys: " + ", ".join(extra_names))

        try:
            return [float(features[name]) for name in self.feature_names]
        except (TypeError, ValueError) as exc:
            raise ValueError("'features' object values must be numeric") from exc


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
    payload_schema = payload.get("schema")

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

    feature_names: list[str] | None = None
    if payload_schema is not None:
        if not isinstance(payload_schema, dict):
            raise ValueError(f"Model '{model_id}' has invalid 'schema' section")

        if payload_schema.get("schema_version") != "1":
            raise ValueError(
                f"Model '{model_id}' schema_version must be '1' when schema is set"
            )

        schema_features = payload_schema.get("features")
        if not isinstance(schema_features, list) or not schema_features:
            raise ValueError(
                f"Model '{model_id}' schema must define a non-empty 'features' list"
            )

        parsed_names: list[str] = []
        for item in schema_features:
            if not isinstance(item, dict):
                raise ValueError(f"Model '{model_id}' schema features must be objects")

            name = item.get("name")
            dtype = item.get("dtype")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(
                    f"Model '{model_id}' schema feature names must be non-empty strings"
                )
            if dtype != "float":
                raise ValueError(
                    f"Model '{model_id}' schema feature '{name}' must have dtype "
                    f"'float'"
                )

            parsed_names.append(name)

        if len(parsed_names) != len(set(parsed_names)):
            raise ValueError(f"Model '{model_id}' schema feature names must be unique")

        if len(parsed_names) != len(weights):
            raise ValueError(
                f"Model '{model_id}' schema feature count must match weights length"
            )

        feature_names = parsed_names

    return LinearModel(
        model_id=model_id,
        type=payload_type,
        bias=bias,
        weights=weights,
        feature_names=feature_names,
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
