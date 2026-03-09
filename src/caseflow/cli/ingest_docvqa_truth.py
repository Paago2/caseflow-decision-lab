from __future__ import annotations

import argparse

from caseflow.pipelines.docvqa_truth_ingest import ingest_docvqa_truth_to_minio


def main() -> None:
    p = argparse.ArgumentParser(
        description="Ingest DocVQA OCR + QAS source truth JSONs to MinIO"
    )
    p.add_argument("--bronze-images", required=True, help="Glob to DocVQA images")
    p.add_argument(
        "--bronze-ocr-dir",
        required=True,
        help="Path to DocVQA OCR json dir",
    )
    p.add_argument(
        "--bronze-qas-dir",
        required=True,
        help="Path to DocVQA QAS json dir",
    )
    p.add_argument("--bucket", default="lake")
    p.add_argument("--split", required=True, help="train|val|test or custom label")
    p.add_argument("--run-id", default="sample")
    p.add_argument("--limit-docs", type=int, default=0, help="0 means no limit")
    args = p.parse_args()

    limit_docs = None if int(args.limit_docs) <= 0 else int(args.limit_docs)

    ingest_docvqa_truth_to_minio(
        bronze_images=str(args.bronze_images),
        bronze_ocr_dir=str(args.bronze_ocr_dir),
        bronze_qas_dir=str(args.bronze_qas_dir),
        bucket=str(args.bucket),
        split=str(args.split),
        run_id=str(args.run_id),
        limit_docs=limit_docs,
    )


if __name__ == "__main__":
    main()
