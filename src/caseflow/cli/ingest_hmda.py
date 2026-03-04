from __future__ import annotations

import argparse
from pathlib import Path

from caseflow.pipelines.hmda_ingest import ingest_hmda_2017_to_minio


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest HMDA Bronze CSV into Silver/Gold on MinIO"
    )

    parser.add_argument("--year", type=int, default=2017)
    parser.add_argument(
        "--bronze-csv",
        type=Path,
        default=Path(
            "data/00_raw/finance_housing/hmda/2017/hmda_2017_nationwide_all-records_labels.csv"
        ),
    )
    parser.add_argument("--bucket", type=str, default="lake")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--mode", choices=["skip", "overwrite"], default="skip")
    parser.add_argument("--run-id", type=str, default="default")

    args = parser.parse_args()

    ingest_hmda_2017_to_minio(
        bronze_csv_path=args.bronze_csv,
        bucket=args.bucket,
        year=args.year,
        limit_rows=args.limit or None,
        mode=args.mode,
        run_id=args.run_id,
    )


if __name__ == "__main__":
    main()
