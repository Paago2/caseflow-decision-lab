from __future__ import annotations

import argparse

from caseflow.pipelines.sroie_truth_ingest import ingest_sroie_truth_to_minio


def main() -> None:
    p = argparse.ArgumentParser(
        description="Ingest SROIE source truth (boxes + entities) to MinIO"
    )
    p.add_argument("--bronze-images", required=True, help="Glob to SROIE images")
    p.add_argument("--bronze-boxes-dir", required=True, help="Path to SROIE box dir")
    p.add_argument(
        "--bronze-entities-dir", required=True, help="Path to SROIE entities dir"
    )
    p.add_argument("--bucket", default="lake")
    p.add_argument("--split", required=True, choices=["train", "test"])
    p.add_argument("--run-id", default="sample")
    p.add_argument("--limit-docs", type=int, default=0, help="0 means no limit")
    args = p.parse_args()

    limit_docs = None if int(args.limit_docs) <= 0 else int(args.limit_docs)

    ingest_sroie_truth_to_minio(
        bronze_images=str(args.bronze_images),
        bronze_boxes_dir=str(args.bronze_boxes_dir),
        bronze_entities_dir=str(args.bronze_entities_dir),
        bucket=str(args.bucket),
        split=str(args.split),
        run_id=str(args.run_id),
        limit_docs=limit_docs,
    )


if __name__ == "__main__":
    main()
