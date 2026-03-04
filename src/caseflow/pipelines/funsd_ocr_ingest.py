from __future__ import annotations

import glob
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from caseflow.repo.minio_s3 import exists, make_minio_s3_client, put_json

OcrEngine = Literal["noop", "tesseract"]


@dataclass
class FunsdOcrIngestResult:
    dataset: str
    split: str
    run_id: str
    limit_docs: int | None
    docs_seen: int
    ocr_written: int
    truth_written: int
    timings: dict[str, float]
    paths: dict[str, str]


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def doc_id_from_bytes(b: bytes) -> str:
    return _sha256_hex(b)[:16]


def _content_type_for_image(path: Path) -> str:
    s = path.suffix.lower()
    if s == ".png":
        return "image/png"
    if s in (".jpg", ".jpeg"):
        return "image/jpeg"
    return "application/octet-stream"


def build_ocr_v1_json(
    *,
    split: str,
    run_id: str,
    doc_id: str,
    filename: str,
    sha256: str,
    content_type: str,
    engine: str,
    text: str,
    duration_ms: int,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "ocr.v1",
        "dataset": "funsd",
        "split": split,
        "run_id": run_id,
        "doc_id": doc_id,
        "source": {
            "filename": filename,
            "sha256": sha256,
            "content_type": content_type,
        },
        "ocr": {
            "engine": engine,
            "text": text,
            "pages": [{"page": 1, "text": text}],
            "meta": {
                "duration_ms": int(duration_ms),
                "warnings": warnings or [],
                "errors": errors or [],
            },
        },
    }


def build_truth_funsd_v1_json(
    *,
    split: str,
    run_id: str,
    doc_id: str,
    filename: str,
    sha256: str,
    truth_obj: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "truth.funsd.v1",
        "dataset": "funsd",
        "split": split,
        "run_id": run_id,
        "doc_id": doc_id,
        "source": {"filename": filename, "sha256": sha256},
        "truth": truth_obj,
    }


def _ocr_noop(_: bytes) -> tuple[str, dict[str, Any]]:
    return "", {"engine": "noop"}


def _ocr_tesseract(image_bytes: bytes) -> tuple[str, dict[str, Any]]:
    try:
        from io import BytesIO

        import pytesseract
        from PIL import Image
        from pytesseract import TesseractNotFoundError
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Missing OCR deps. Install: uv add pytesseract Pillow"
        ) from e

    try:
        img = Image.open(BytesIO(image_bytes))
        # ensure we load it now so errors happen here
        img.load()
        text = pytesseract.image_to_string(img)
        return text or "", {"engine": "tesseract"}
    except TesseractNotFoundError as e:  # pragma: no cover
        raise RuntimeError(
            "Tesseract binary not found. Install tesseract-ocr in the api "
            "container/image or run with --ocr-engine noop."
        ) from e


def ingest_funsd_ocr_to_minio(
    *,
    bronze_images: str,
    bronze_annotations_dir: str,
    bucket: str,
    split: str,
    run_id: str,
    limit_docs: int | None,
    ocr_engine: OcrEngine,
) -> FunsdOcrIngestResult:
    client = make_minio_s3_client()

    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    print(
        {
            "event": "funsd_stage_start",
            "stage": "discover",
            "split": split,
            "run_id": run_id,
            "bronze_images": bronze_images,
            "bronze_annotations_dir": bronze_annotations_dir,
            "limit_docs": limit_docs,
            "ocr_engine": ocr_engine,
        }
    )

    # Resolve glob string deterministically
    files = [Path(p) for p in glob.glob(bronze_images)]
    files = [p for p in files if p.is_file() and p.name != ".DS_Store"]
    files = [p for p in files if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
    files.sort(key=lambda p: str(p))

    if limit_docs is not None:
        files = files[: int(limit_docs)]

    timings["discover"] = round(time.perf_counter() - t0, 6)

    ocr_prefix = f"docs/silver_ocr/funsd/{split}/run_id={run_id}"
    truth_prefix = f"docs/silver_truth/funsd/{split}/run_id={run_id}"
    ann_dir = Path(bronze_annotations_dir)

    docs_seen = 0
    ocr_written = 0
    truth_written = 0

    # -----------------------------
    # OCR + write loop
    # -----------------------------
    print(
        {
            "event": "funsd_stage_start",
            "stage": "ocr_write",
            "split": split,
            "run_id": run_id,
            "count_candidates": len(files),
            "ocr_prefix": f"s3://{bucket}/{ocr_prefix}",
        }
    )
    t_ocr = time.perf_counter()

    for img_path in files:
        docs_seen += 1
        b = img_path.read_bytes()
        sha = _sha256_hex(b)
        did = sha[:16]

        ct = _content_type_for_image(img_path)

        # OCR
        t_doc = time.perf_counter()
        warnings: list[str] = []
        errors: list[str] = []

        if ocr_engine == "noop":
            text, _meta = _ocr_noop(b)
        elif ocr_engine == "tesseract":
            try:
                text, _meta = _ocr_tesseract(b)
            except Exception:
                # In enterprise pipelines, fail fast is acceptable.
                # If you prefer "continue on error", we can change this later.
                raise
        else:  # pragma: no cover
            raise ValueError(f"Unsupported ocr_engine: {ocr_engine}")

        duration_ms = int((time.perf_counter() - t_doc) * 1000)

        ocr_json = build_ocr_v1_json(
            split=split,
            run_id=run_id,
            doc_id=did,
            filename=img_path.name,
            sha256=sha,
            content_type=ct,
            engine=ocr_engine,
            text=text,
            duration_ms=duration_ms,
            warnings=warnings,
            errors=errors,
        )

        ocr_key = f"{ocr_prefix}/{did}/ocr.v1.json"
        put_json(client, bucket, ocr_key, ocr_json)
        # Lightweight existence check
        if not exists(client, bucket, ocr_key):
            raise RuntimeError(
                f"Write failed or not visible in MinIO: s3://{bucket}/{ocr_key}"
            )
        ocr_written += 1

        # Truth sidecar (optional)
        ann_path = ann_dir / f"{img_path.stem}.json"
        if ann_path.exists():
            truth_obj = json.loads(ann_path.read_text(encoding="utf-8"))
            truth_json = build_truth_funsd_v1_json(
                split=split,
                run_id=run_id,
                doc_id=did,
                filename=ann_path.name,
                sha256=_sha256_hex(ann_path.read_bytes()),
                truth_obj=truth_obj,
            )
            truth_key = f"{truth_prefix}/{did}/truth.funsd.v1.json"
            put_json(client, bucket, truth_key, truth_json)
            if not exists(client, bucket, truth_key):
                raise RuntimeError(
                    f"Write failed or not visible in MinIO: s3://{bucket}/{truth_key}"
                )
            truth_written += 1

    timings["ocr_write_loop"] = round(time.perf_counter() - t_ocr, 6)
    timings["total"] = round(time.perf_counter() - t0, 6)

    result = FunsdOcrIngestResult(
        dataset="funsd",
        split=split,
        run_id=run_id,
        limit_docs=limit_docs,
        docs_seen=docs_seen,
        ocr_written=ocr_written,
        truth_written=truth_written,
        timings=timings,
        paths={
            "ocr_prefix": f"s3://{bucket}/{ocr_prefix}",
            "truth_prefix": f"s3://{bucket}/{truth_prefix}",
        },
    )

    print(
        {
            "event": "funsd_ingest_complete",
            "dataset": result.dataset,
            "split": result.split,
            "run_id": result.run_id,
            "limit_docs": result.limit_docs,
            "counts": {
                "docs_seen": result.docs_seen,
                "ocr_written": result.ocr_written,
                "truth_written": result.truth_written,
            },
            "timings": result.timings,
            "paths": result.paths,
        }
    )

    return result
