from __future__ import annotations

import argparse
from pathlib import Path

from caseflow.pipelines.lending_club_ingest import ingest_lending_club_to_minio


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest Lending Club CSV -> Silver Parquet on MinIO"
    )
    parser.add_argument("--bronze", type=Path, required=True)
    parser.add_argument("--bucket", type=str, default="lake")
    parser.add_argument("--run-id", type=str, default="sample")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    ingest_lending_club_to_minio(
        bronze_csv_path=args.bronze,
        bucket=args.bucket,
        run_id=args.run_id,
        limit_rows=args.limit or None,
    )


if __name__ == "__main__":
    main()
