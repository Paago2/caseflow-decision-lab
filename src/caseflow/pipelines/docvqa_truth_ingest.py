from __future__ import annotations

import glob
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from caseflow.repo.minio_s3 import exists, make_minio_s3_client, put_json


@dataclass
class DocVqaTruthIngestResult:
    dataset: str
    split: str
    run_id: str
    limit_docs: int | None
    images_seen: int
    ocr_written: int
    qas_written: int
    manifest_written: int
    timings: dict[str, float]
    paths: dict[str, str]


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _doc_id_from_image_path(path: Path) -> str:
    # Keep doc_id human-readable and stable for joins
    return path.stem


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _content_type_for_image(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return "application/octet-stream"


def _build_docvqa_ocr_source_v1(
    *,
    split: str,
    run_id: str,
    doc_id: str,
    image_filename: str,
    image_sha256: str,
    content_type: str,
    ocr_filename: str,
    ocr_sha256: str,
    ocr_obj: Any,
) -> dict[str, Any]:
    return {
        "schema_version": "ocr.source.v1",
        "dataset": "docvqa",
        "split": split,
        "run_id": run_id,
        "doc_id": doc_id,
        "source": {
            "image_filename": image_filename,
            "image_sha256": image_sha256,
            "content_type": content_type,
            "ocr_filename": ocr_filename,
            "ocr_sha256": ocr_sha256,
        },
        "ocr_source": ocr_obj,
    }


def _build_docvqa_qas_v1(
    *,
    split: str,
    run_id: str,
    qas_filename: str,
    qas_sha256: str,
    qas_obj: Any,
) -> dict[str, Any]:
    return {
        "schema_version": "qas.source.v1",
        "dataset": "docvqa",
        "split": split,
        "run_id": run_id,
        "source": {
            "qas_filename": qas_filename,
            "qas_sha256": qas_sha256,
        },
        "qas_source": qas_obj,
    }


def _build_docvqa_manifest_v1(
    *,
    split: str,
    run_id: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "manifest.v1",
        "dataset": "docvqa",
        "split": split,
        "run_id": run_id,
        "count": len(rows),
        "documents": rows,
    }


def ingest_docvqa_truth_to_minio(
    *,
    bronze_images: str,
    bronze_ocr_dir: str,
    bronze_qas_dir: str,
    bucket: str,
    split: str,
    run_id: str,
    limit_docs: int | None,
) -> DocVqaTruthIngestResult:
    client = make_minio_s3_client()

    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    print(
        {
            "event": "docvqa_stage_start",
            "stage": "discover",
            "split": split,
            "run_id": run_id,
            "bronze_images": bronze_images,
            "bronze_ocr_dir": bronze_ocr_dir,
            "bronze_qas_dir": bronze_qas_dir,
            "limit_docs": limit_docs,
        }
    )

    image_files = [Path(p) for p in glob.glob(bronze_images)]
    image_files = [
        p
        for p in image_files
        if p.is_file()
        and p.name != ".DS_Store"
        and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    image_files.sort(key=lambda p: str(p))

    if limit_docs is not None:
        image_files = image_files[: int(limit_docs)]

    ocr_dir = Path(bronze_ocr_dir)
    qas_dir = Path(bronze_qas_dir)

    timings["discover"] = round(time.perf_counter() - t0, 6)

    ocr_prefix = f"docs/silver_ocr/docvqa/{split}/run_id={run_id}"
    qas_prefix = f"docs/silver_qa/docvqa/{split}/run_id={run_id}"
    manifest_prefix = f"docs/silver_index/docvqa/{split}/run_id={run_id}"

    images_seen = 0
    ocr_written = 0
    qas_written = 0
    manifest_written = 0

    manifest_rows: list[dict[str, Any]] = []

    # --------------------------------
    # Stage 1: image -> paired OCR JSON
    # --------------------------------
    print(
        {
            "event": "docvqa_stage_start",
            "stage": "ocr_source_write",
            "split": split,
            "run_id": run_id,
            "count_candidates": len(image_files),
            "ocr_prefix": f"s3://{bucket}/{ocr_prefix}",
        }
    )
    t_stage = time.perf_counter()

    for image_path in image_files:
        images_seen += 1

        doc_id = _doc_id_from_image_path(image_path)
        image_bytes = image_path.read_bytes()
        image_sha = _sha256_hex(image_bytes)
        content_type = _content_type_for_image(image_path)

        ocr_path = ocr_dir / f"{doc_id}.json"
        has_ocr = ocr_path.exists()

        if has_ocr:
            ocr_bytes = ocr_path.read_bytes()
            ocr_sha = _sha256_hex(ocr_bytes)
            ocr_obj = _read_json(ocr_path)

            ocr_json = _build_docvqa_ocr_source_v1(
                split=split,
                run_id=run_id,
                doc_id=doc_id,
                image_filename=image_path.name,
                image_sha256=image_sha,
                content_type=content_type,
                ocr_filename=ocr_path.name,
                ocr_sha256=ocr_sha,
                ocr_obj=ocr_obj,
            )

            ocr_key = f"{ocr_prefix}/{doc_id}/ocr.source.v1.json"
            put_json(client, bucket, ocr_key, ocr_json)

            if not exists(client, bucket, ocr_key):
                raise RuntimeError(
                    f"Write failed or not visible in MinIO: s3://{bucket}/{ocr_key}"
                )

            ocr_written += 1

        manifest_rows.append(
            {
                "doc_id": doc_id,
                "image_filename": image_path.name,
                "image_sha256": image_sha,
                "content_type": content_type,
                "has_ocr": has_ocr,
                "ocr_filename": ocr_path.name if has_ocr else None,
            }
        )

    timings["ocr_source_write"] = round(time.perf_counter() - t_stage, 6)

    # --------------------------------
    # Stage 2: QAS source JSON files
    # --------------------------------
    print(
        {
            "event": "docvqa_stage_start",
            "stage": "qas_source_write",
            "split": split,
            "run_id": run_id,
            "qas_prefix": f"s3://{bucket}/{qas_prefix}",
        }
    )
    t_stage = time.perf_counter()

    qas_files = [p for p in qas_dir.rglob("*.json") if p.is_file()]
    qas_files.sort(key=lambda p: str(p))

    for qas_path in qas_files:
        qas_bytes = qas_path.read_bytes()
        qas_sha = _sha256_hex(qas_bytes)
        qas_obj = _read_json(qas_path)

        qas_json = _build_docvqa_qas_v1(
            split=split,
            run_id=run_id,
            qas_filename=qas_path.name,
            qas_sha256=qas_sha,
            qas_obj=qas_obj,
        )

        qas_key = f"{qas_prefix}/{qas_path.stem}/qas.source.v1.json"
        put_json(client, bucket, qas_key, qas_json)

        if not exists(client, bucket, qas_key):
            raise RuntimeError(
                f"Write failed or not visible in MinIO: s3://{bucket}/{qas_key}"
            )

        qas_written += 1

    timings["qas_source_write"] = round(time.perf_counter() - t_stage, 6)

    # --------------------------------
    # Stage 3: manifest
    # --------------------------------
    print(
        {
            "event": "docvqa_stage_start",
            "stage": "manifest_write",
            "split": split,
            "run_id": run_id,
            "manifest_prefix": f"s3://{bucket}/{manifest_prefix}",
        }
    )
    t_stage = time.perf_counter()

    manifest_json = _build_docvqa_manifest_v1(
        split=split,
        run_id=run_id,
        rows=manifest_rows,
    )
    manifest_key = f"{manifest_prefix}/manifest.v1.json"
    put_json(client, bucket, manifest_key, manifest_json)

    if not exists(client, bucket, manifest_key):
        raise RuntimeError(
            f"Write failed or not visible in MinIO: s3://{bucket}/{manifest_key}"
        )

    manifest_written = 1
    timings["manifest_write"] = round(time.perf_counter() - t_stage, 6)
    timings["total"] = round(time.perf_counter() - t0, 6)

    result = DocVqaTruthIngestResult(
        dataset="docvqa",
        split=split,
        run_id=run_id,
        limit_docs=limit_docs,
        images_seen=images_seen,
        ocr_written=ocr_written,
        qas_written=qas_written,
        manifest_written=manifest_written,
        timings=timings,
        paths={
            "ocr_prefix": f"s3://{bucket}/{ocr_prefix}",
            "qas_prefix": f"s3://{bucket}/{qas_prefix}",
            "manifest_key": f"s3://{bucket}/{manifest_key}",
        },
    )

    print(
        {
            "event": "docvqa_ingest_complete",
            "dataset": result.dataset,
            "split": result.split,
            "run_id": result.run_id,
            "limit_docs": result.limit_docs,
            "counts": {
                "images_seen": result.images_seen,
                "ocr_written": result.ocr_written,
                "qas_written": result.qas_written,
                "manifest_written": result.manifest_written,
            },
            "timings": result.timings,
            "paths": result.paths,
        }
    )

    return result
