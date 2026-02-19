from pathlib import Path

import pytest

from caseflow.ml.datasets_contract import load_dataset_contract


def test_load_dataset_contract_rejects_missing_required_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "datasets.yaml"
    config_path.write_text(
        """
datasets:
  - name: bad_dataset
    path: data/raw/example.csv
    target_column: target
    schema_version: "2"
""".strip() + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_dataset_contract(config_path=config_path, dataset_name="bad_dataset")

    assert "dataset entry missing required fields" in str(exc_info.value)
    assert "feature_columns" in str(exc_info.value)
