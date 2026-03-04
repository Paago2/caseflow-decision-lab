from __future__ import annotations

import argparse

from caseflow.pipelines.freddie_ingest import ingest_freddie_crt_lld_to_minio


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--bronze",
        required=True,
        help="Path OR glob to Freddie CRT lld txt files (e.g. data/.../*.txt)",
    )
    p.add_argument("--bucket", default="lake")
    p.add_argument("--dataset-id", required=True, help="e.g. 2025-12 or 15SC01")
    p.add_argument("--run-id", default="sample")
    p.add_argument("--limit", type=int, default=200_000, help="0 means no limit")
    args = p.parse_args()

    limit_rows = None if int(args.limit) <= 0 else int(args.limit)

    ingest_freddie_crt_lld_to_minio(
        bronze=str(args.bronze),  # <-- IMPORTANT: keep as string, supports globs
        bucket=str(args.bucket),
        dataset_id=str(args.dataset_id),
        run_id=str(args.run_id),
        limit_rows=limit_rows,
    )


if __name__ == "__main__":
    main()
