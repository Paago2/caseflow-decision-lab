from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DatasetContract:
    name: str
    path: str
    target_column: str
    feature_columns: list[str]
    schema_version: str


def load_dataset_contract(config_path: Path, dataset_name: str) -> DatasetContract:
    payload = _load_yaml(config_path)

    datasets = payload.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("datasets config must define a non-empty 'datasets' list")

    for item in datasets:
        if not isinstance(item, dict):
            raise ValueError("each dataset entry must be an object")

        if item.get("name") == dataset_name:
            return _validate_dataset_entry(item)

    raise ValueError(f"dataset '{dataset_name}' not found in config")


def _load_yaml(config_path: Path) -> dict:
    if not config_path.is_file():
        raise ValueError(f"datasets config not found: {config_path}")

    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in datasets config: {config_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("datasets config root must be a YAML mapping")

    return payload


def _validate_dataset_entry(item: dict) -> DatasetContract:
    required_fields = [
        "name",
        "path",
        "target_column",
        "feature_columns",
        "schema_version",
    ]
    missing = [field for field in required_fields if field not in item]
    if missing:
        raise ValueError(
            "dataset entry missing required fields: " + ", ".join(sorted(missing))
        )

    name = item["name"]
    path = item["path"]
    target_column = item["target_column"]
    feature_columns = item["feature_columns"]
    schema_version = item["schema_version"]

    if not isinstance(name, str) or not name.strip():
        raise ValueError("dataset field 'name' must be a non-empty string")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("dataset field 'path' must be a non-empty string")
    if not isinstance(target_column, str) or not target_column.strip():
        raise ValueError("dataset field 'target_column' must be a non-empty string")
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("dataset field 'schema_version' must be a non-empty string")

    if not isinstance(feature_columns, list) or not feature_columns:
        raise ValueError("dataset field 'feature_columns' must be a non-empty list")

    cleaned_features: list[str] = []
    for value in feature_columns:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("dataset field 'feature_columns' must contain strings")
        cleaned_features.append(value)

    return DatasetContract(
        name=name,
        path=path,
        target_column=target_column,
        feature_columns=cleaned_features,
        schema_version=schema_version,
    )
