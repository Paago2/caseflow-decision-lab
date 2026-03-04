from __future__ import annotations

import argparse

from caseflow.pipelines.funsd_ocr_ingest import ingest_funsd_ocr_to_minio


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--bronze-images", required=True, help="Glob to FUNSD images (*.png/*.jpg)"
    )
    p.add_argument(
        "--bronze-annotations-dir", required=True, help="Path to FUNSD annotations dir"
    )
    p.add_argument("--bucket", default="lake")
    p.add_argument("--split", required=True, choices=["training", "testing"])
    p.add_argument("--run-id", default="sample")
    p.add_argument("--limit-docs", type=int, default=0, help="0 means no limit")
    p.add_argument("--ocr-engine", default="noop", choices=["noop", "tesseract"])
    args = p.parse_args()

    limit_docs = None if int(args.limit_docs) <= 0 else int(args.limit_docs)

    ingest_funsd_ocr_to_minio(
        bronze_images=str(args.bronze_images),
        bronze_annotations_dir=str(args.bronze_annotations_dir),
        bucket=str(args.bucket),
        split=str(args.split),
        run_id=str(args.run_id),
        limit_docs=limit_docs,
        ocr_engine=str(args.ocr_engine),  # type: ignore[arg-type]
    )


if __name__ == "__main__":
    main()
