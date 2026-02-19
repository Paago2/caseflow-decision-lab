"""Experiment 007: ingest + validate a CSV dataset contract and write parquet output.

Reads dataset metadata from configs/datasets.yaml, validates required columns,
prints quality summary, and writes data/processed/<dataset_name>.parquet.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from caseflow.ml.datasets_contract import load_dataset_contract


def main() -> None:
    config_path = Path("configs") / "datasets.yaml"
    dataset_name = "example_diabetes_csv"

    try:
        contract = load_dataset_contract(
            config_path=config_path,
            dataset_name=dataset_name,
        )
    except ValueError as exc:
        print(f"[error] invalid dataset config: {exc}")
        raise SystemExit(1) from exc

    csv_path = Path(contract.path)
    if not csv_path.is_file():
        print("[error] dataset CSV not found")
        print(f"[hint] expected path: {csv_path}")
        print("[hint] place your CSV at the path above and rerun: make exp-007")
        raise SystemExit(1)

    dataframe = pd.read_csv(csv_path)

    if not contract.feature_columns:
        print("[error] dataset contract has empty feature_columns")
        raise SystemExit(1)

    required_columns = contract.feature_columns + [contract.target_column]
    missing_columns = sorted(
        column for column in required_columns if column not in dataframe.columns
    )
    if missing_columns:
        print(
            "[error] dataset is missing required columns: " + ", ".join(missing_columns)
        )
        raise SystemExit(1)

    print(f"[info] dataset_name={contract.name}")
    print(f"[info] row_count={len(dataframe)}")

    missing_value_counts = dataframe[required_columns].isna().sum().to_dict()
    print("[info] missing_values=")
    for column_name in required_columns:
        print(f"  - {column_name}: {int(missing_value_counts[column_name])}")

    dtype_map = dataframe[required_columns].dtypes.astype(str).to_dict()
    print("[info] dtypes=")
    for column_name in required_columns:
        print(f"  - {column_name}: {dtype_map[column_name]}")

    target_series = dataframe[contract.target_column]
    print(
        "[info] target_stats="
        f" min={float(target_series.min()):.6f}"
        f" max={float(target_series.max()):.6f}"
        f" mean={float(target_series.mean()):.6f}"
    )

    output_path = Path("data") / "processed" / f"{contract.name}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        dataframe.to_parquet(output_path, index=False)
    except Exception as exc:  # pragma: no cover
        print("[error] failed to write parquet output")
        print("[hint] install a parquet engine (for example: pyarrow) and retry")
        print(f"[detail] {exc}")
        raise SystemExit(1) from exc

    print(f"[info] wrote_processed_parquet={output_path}")


if __name__ == "__main__":
    sys.exit(main())
