from __future__ import annotations

import argparse

from caseflow.pipelines.synthdog_truth_ingest import (
    ingest_synthdog_truth_to_minio,
)


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest SynthDog source truth to MinIO")
    p.add_argument("--bronze-data-dir", required=True, help="Path to synthdog data dir")
    p.add_argument(
        "--bronze-dataset-info",
        required=True,
        help="Path to synthdog dataset_infos.json",
    )
    p.add_argument("--bucket", default="lake")
    p.add_argument("--run-id", default="sample")
    p.add_argument("--limit-files", type=int, default=0, help="0 means no limit")
    args = p.parse_args()

    limit_files = None if int(args.limit_files) <= 0 else int(args.limit_files)

    ingest_synthdog_truth_to_minio(
        bronze_data_dir=str(args.bronze_data_dir),
        bronze_dataset_info=str(args.bronze_dataset_info),
        bucket=str(args.bucket),
        run_id=str(args.run_id),
        limit_files=limit_files,
    )


if __name__ == "__main__":
    main()
