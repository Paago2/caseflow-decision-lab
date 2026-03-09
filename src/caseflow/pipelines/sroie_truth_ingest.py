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
class SroieTruthIngestResult:
    dataset: str
    split: str
    run_id: str
    limit_docs: int | None
    images_seen: int
    boxes_written: int
    entities_written: int
    manifest_written: int
    timings: dict[str, float]
    paths: dict[str, str]


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _doc_id_from_path(path: Path) -> str:
    return path.stem


def _read_text(path: Path) -> str:
    """
    Read text files from SROIE dataset.

    Some files contain non-UTF8 characters (e.g. £ € ¥),
    so we try UTF-8 first and fall back to latin-1.
    """
    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1").strip()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _content_type_for_image(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".jpg":
        return "image/jpeg"
    if suffix == ".jpeg":
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    return "application/octet-stream"


def _parse_sroie_box_text(raw_text: str) -> list[dict[str, Any]]:
    """
    SROIE box files are usually line-based text.
    Common pattern:
      x1,y1,x2,y2,x3,y3,x4,y4,text
    We keep a tolerant parser so v1 doesn't break on odd rows.
    """
    rows: list[dict[str, Any]] = []

    if not raw_text:
        return rows

    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        parts = line.split(",")
        if len(parts) < 9:
            rows.append(
                {
                    "line_no": line_no,
                    "raw": line,
                    "parsed": False,
                    "warning": "expected at least 9 comma-separated parts",
                }
            )
            continue

        coord_parts = parts[:8]
        text = ",".join(parts[8:]).strip()

        try:
            coords = [int(x) for x in coord_parts]
            rows.append(
                {
                    "line_no": line_no,
                    "parsed": True,
                    "polygon": {
                        "x1": coords[0],
                        "y1": coords[1],
                        "x2": coords[2],
                        "y2": coords[3],
                        "x3": coords[4],
                        "y3": coords[5],
                        "x4": coords[6],
                        "y4": coords[7],
                    },
                    "text": text,
                }
            )
        except ValueError:
            rows.append(
                {
                    "line_no": line_no,
                    "raw": line,
                    "parsed": False,
                    "warning": "failed to cast coordinates to int",
                }
            )

    return rows


def _build_sroie_boxes_source_v1(
    *,
    split: str,
    run_id: str,
    doc_id: str,
    image_filename: str,
    image_sha256: str,
    content_type: str,
    boxes_filename: str,
    boxes_sha256: str,
    boxes_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "boxes.source.v1",
        "dataset": "sroie",
        "split": split,
        "run_id": run_id,
        "doc_id": doc_id,
        "source": {
            "image_filename": image_filename,
            "image_sha256": image_sha256,
            "content_type": content_type,
            "boxes_filename": boxes_filename,
            "boxes_sha256": boxes_sha256,
        },
        "boxes_source": boxes_rows,
    }


def _build_sroie_entities_source_v1(
    *,
    split: str,
    run_id: str,
    doc_id: str,
    image_filename: str,
    image_sha256: str,
    content_type: str,
    entities_filename: str,
    entities_sha256: str,
    entities_obj: Any,
) -> dict[str, Any]:
    return {
        "schema_version": "entities.source.v1",
        "dataset": "sroie",
        "split": split,
        "run_id": run_id,
        "doc_id": doc_id,
        "source": {
            "image_filename": image_filename,
            "image_sha256": image_sha256,
            "content_type": content_type,
            "entities_filename": entities_filename,
            "entities_sha256": entities_sha256,
        },
        "entities_source": entities_obj,
    }


def _build_sroie_manifest_v1(
    *,
    split: str,
    run_id: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "manifest.v1",
        "dataset": "sroie",
        "split": split,
        "run_id": run_id,
        "count": len(rows),
        "documents": rows,
    }


def ingest_sroie_truth_to_minio(
    *,
    bronze_images: str,
    bronze_boxes_dir: str,
    bronze_entities_dir: str,
    bucket: str,
    split: str,
    run_id: str,
    limit_docs: int | None,
) -> SroieTruthIngestResult:
    client = make_minio_s3_client()

    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    print(
        {
            "event": "sroie_stage_start",
            "stage": "discover",
            "split": split,
            "run_id": run_id,
            "bronze_images": bronze_images,
            "bronze_boxes_dir": bronze_boxes_dir,
            "bronze_entities_dir": bronze_entities_dir,
            "limit_docs": limit_docs,
        }
    )

    image_files = [Path(p) for p in glob.glob(bronze_images)]
    image_files = [
        p
        for p in image_files
        if p.is_file()
        and p.name != ".DS_Store"
        and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ]
    image_files.sort(key=lambda p: str(p))

    if limit_docs is not None:
        image_files = image_files[: int(limit_docs)]

    boxes_dir = Path(bronze_boxes_dir)
    entities_dir = Path(bronze_entities_dir)

    timings["discover"] = round(time.perf_counter() - t0, 6)

    boxes_prefix = f"docs/silver_truth/sroie/{split}/run_id={run_id}"
    entities_prefix = f"docs/silver_truth/sroie/{split}/run_id={run_id}"
    manifest_prefix = f"docs/silver_index/sroie/{split}/run_id={run_id}"

    images_seen = 0
    boxes_written = 0
    entities_written = 0
    manifest_written = 0

    manifest_rows: list[dict[str, Any]] = []

    print(
        {
            "event": "sroie_stage_start",
            "stage": "truth_write",
            "split": split,
            "run_id": run_id,
            "count_candidates": len(image_files),
            "boxes_prefix": f"s3://{bucket}/{boxes_prefix}",
            "entities_prefix": f"s3://{bucket}/{entities_prefix}",
        }
    )
    t_stage = time.perf_counter()

    for image_path in image_files:
        images_seen += 1

        doc_id = _doc_id_from_path(image_path)
        image_bytes = image_path.read_bytes()
        image_sha = _sha256_hex(image_bytes)
        content_type = _content_type_for_image(image_path)

        box_path = boxes_dir / f"{doc_id}.txt"
        entities_path = entities_dir / f"{doc_id}.txt"

        has_boxes = box_path.exists()
        has_entities = entities_path.exists()

        if has_boxes:
            box_bytes = box_path.read_bytes()
            box_sha = _sha256_hex(box_bytes)
            box_rows = _parse_sroie_box_text(_read_text(box_path))

            boxes_json = _build_sroie_boxes_source_v1(
                split=split,
                run_id=run_id,
                doc_id=doc_id,
                image_filename=image_path.name,
                image_sha256=image_sha,
                content_type=content_type,
                boxes_filename=box_path.name,
                boxes_sha256=box_sha,
                boxes_rows=box_rows,
            )

            boxes_key = f"{boxes_prefix}/{doc_id}/boxes.source.v1.json"
            put_json(client, bucket, boxes_key, boxes_json)
            if not exists(client, bucket, boxes_key):
                raise RuntimeError(
                    f"Write failed or not visible in MinIO: s3://{bucket}/{boxes_key}"
                )
            boxes_written += 1

        if has_entities:
            entities_bytes = entities_path.read_bytes()
            entities_sha = _sha256_hex(entities_bytes)

            # SROIE entities files are often JSON-like but may also be plain text.
            # v1 keeps both modes safe.
            try:
                entities_obj = _read_json(entities_path)
            except json.JSONDecodeError:
                entities_obj = {"raw_text": _read_text(entities_path)}

            entities_json = _build_sroie_entities_source_v1(
                split=split,
                run_id=run_id,
                doc_id=doc_id,
                image_filename=image_path.name,
                image_sha256=image_sha,
                content_type=content_type,
                entities_filename=entities_path.name,
                entities_sha256=entities_sha,
                entities_obj=entities_obj,
            )

            entities_key = f"{entities_prefix}/{doc_id}/entities.source.v1.json"
            put_json(client, bucket, entities_key, entities_json)
            if not exists(client, bucket, entities_key):
                raise RuntimeError(
                    f"Write failed or not visible in MinIO: s3://{bucket}/{entities_key}"
                )
            entities_written += 1

        manifest_rows.append(
            {
                "doc_id": doc_id,
                "image_filename": image_path.name,
                "image_sha256": image_sha,
                "content_type": content_type,
                "has_boxes": has_boxes,
                "has_entities": has_entities,
                "boxes_filename": box_path.name if has_boxes else None,
                "entities_filename": entities_path.name if has_entities else None,
            }
        )

    timings["truth_write"] = round(time.perf_counter() - t_stage, 6)

    print(
        {
            "event": "sroie_stage_start",
            "stage": "manifest_write",
            "split": split,
            "run_id": run_id,
            "manifest_prefix": f"s3://{bucket}/{manifest_prefix}",
        }
    )
    t_stage = time.perf_counter()

    manifest_json = _build_sroie_manifest_v1(
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

    result = SroieTruthIngestResult(
        dataset="sroie",
        split=split,
        run_id=run_id,
        limit_docs=limit_docs,
        images_seen=images_seen,
        boxes_written=boxes_written,
        entities_written=entities_written,
        manifest_written=manifest_written,
        timings=timings,
        paths={
            "boxes_prefix": f"s3://{bucket}/{boxes_prefix}",
            "entities_prefix": f"s3://{bucket}/{entities_prefix}",
            "manifest_key": f"s3://{bucket}/{manifest_key}",
        },
    )

    print(
        {
            "event": "sroie_ingest_complete",
            "dataset": result.dataset,
            "split": result.split,
            "run_id": result.run_id,
            "limit_docs": result.limit_docs,
            "counts": {
                "images_seen": result.images_seen,
                "boxes_written": result.boxes_written,
                "entities_written": result.entities_written,
                "manifest_written": result.manifest_written,
            },
            "timings": result.timings,
            "paths": result.paths,
        }
    )

    return result
