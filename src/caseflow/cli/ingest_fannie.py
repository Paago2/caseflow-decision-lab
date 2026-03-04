from __future__ import annotations

import argparse
from pathlib import Path

from caseflow.pipelines.fannie_ingest import ingest_fannie_loan_performance_to_minio


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest Fannie raw pipe file -> Silver Parquet on MinIO"
    )
    parser.add_argument("--bronze", type=Path, required=True)
    parser.add_argument("--bucket", type=str, default="lake")
    parser.add_argument("--dataset-id", type=str, default="2025Q1")
    parser.add_argument("--run-id", type=str, default="sample")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    ingest_fannie_loan_performance_to_minio(
        bronze_path=args.bronze,
        bucket=args.bucket,
        dataset_id=args.dataset_id,
        run_id=args.run_id,
        limit_rows=args.limit or None,
    )


if __name__ == "__main__":
    main()
