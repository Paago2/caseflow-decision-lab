from __future__ import annotations

import argparse
from pathlib import Path

from caseflow.pipelines.sanctions_ingest import ingest_sanctions_csv_to_minio


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest sanctions CSV -> Silver Parquet on MinIO"
    )
    parser.add_argument("--bronze", type=Path, required=True)
    parser.add_argument("--bucket", type=str, default="lake")
    parser.add_argument("--category", type=str, required=True)
    parser.add_argument("--dataset-name", type=str, required=True)
    parser.add_argument("--run-id", type=str, default="sample")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    ingest_sanctions_csv_to_minio(
        bronze_csv_path=args.bronze,
        bucket=args.bucket,
        category=args.category,
        dataset_name=args.dataset_name,
        run_id=args.run_id,
        limit_rows=args.limit or None,
    )


if __name__ == "__main__":
    main()
