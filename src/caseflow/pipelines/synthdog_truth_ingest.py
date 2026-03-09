from __future__ import annotations

import hashlib
import json
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from caseflow.repo.minio_s3 import exists, make_minio_s3_client, put_json


@dataclass
class SynthdogTruthIngestResult:
    dataset: str
    run_id: str
    limit_files: int | None
    files_seen: int
    files_uploaded: int
    dataset_info_written: int
    manifest_written: int
    timings: dict[str, float]
    paths: dict[str, str]


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _guess_content_type(path: Path) -> str:
    ct, _ = mimetypes.guess_type(str(path))
    return ct or "application/octet-stream"


def _build_dataset_info_source_v1(
    *,
    run_id: str,
    filename: str,
    sha256: str,
    dataset_info_obj: Any,
) -> dict[str, Any]:
    return {
        "schema_version": "dataset_info.source.v1",
        "dataset": "synthdog_en",
        "run_id": run_id,
        "source": {
            "filename": filename,
            "sha256": sha256,
        },
        "dataset_info_source": dataset_info_obj,
    }


def _build_manifest_v1(
    *,
    run_id: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "manifest.v1",
        "dataset": "synthdog_en",
        "run_id": run_id,
        "count": len(rows),
        "files": rows,
    }


def ingest_synthdog_truth_to_minio(
    *,
    bronze_data_dir: str,
    bronze_dataset_info: str,
    bucket: str,
    run_id: str,
    limit_files: int | None,
) -> SynthdogTruthIngestResult:
    client = make_minio_s3_client()

    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    data_dir = Path(bronze_data_dir)
    dataset_info_path = Path(bronze_dataset_info)

    print(
        {
            "event": "synthdog_stage_start",
            "stage": "discover",
            "run_id": run_id,
            "bronze_data_dir": str(data_dir),
            "bronze_dataset_info": str(dataset_info_path),
            "limit_files": limit_files,
        }
    )

    if not data_dir.exists():
        raise FileNotFoundError(f"data dir not found: {data_dir}")
    if not dataset_info_path.exists():
        raise FileNotFoundError(f"dataset info not found: {dataset_info_path}")

    files = [p for p in data_dir.rglob("*") if p.is_file() and p.name != ".DS_Store"]
    files.sort(key=lambda p: str(p))

    if limit_files is not None:
        files = files[: int(limit_files)]

    timings["discover"] = round(time.perf_counter() - t0, 6)

    truth_prefix = f"docs/silver_truth/synthdog_en/run_id={run_id}"
    manifest_prefix = f"docs/silver_index/synthdog_en/run_id={run_id}"

    files_seen = 0
    files_uploaded = 0
    dataset_info_written = 0
    manifest_written = 0

    manifest_rows: list[dict[str, Any]] = []

    # --------------------------------
    # Stage 1: dataset_infos.json
    # --------------------------------
    print(
        {
            "event": "synthdog_stage_start",
            "stage": "dataset_info_write",
            "run_id": run_id,
            "truth_prefix": f"s3://{bucket}/{truth_prefix}",
        }
    )
    t_stage = time.perf_counter()

    dataset_info_bytes = dataset_info_path.read_bytes()
    dataset_info_sha = _sha256_hex(dataset_info_bytes)
    dataset_info_obj = json.loads(dataset_info_bytes.decode("utf-8"))

    dataset_info_json = _build_dataset_info_source_v1(
        run_id=run_id,
        filename=dataset_info_path.name,
        sha256=dataset_info_sha,
        dataset_info_obj=dataset_info_obj,
    )

    dataset_info_key = (
        f"{truth_prefix}/dataset_infos/{dataset_info_path.stem}.source.v1.json"
    )
    put_json(client, bucket, dataset_info_key, dataset_info_json)

    if not exists(client, bucket, dataset_info_key):
        raise RuntimeError(
            f"Write failed or not visible in MinIO: s3://{bucket}/{dataset_info_key}"
        )

    dataset_info_written = 1
    timings["dataset_info_write"] = round(time.perf_counter() - t_stage, 6)

    # --------------------------------
    # Stage 2: copy data files
    # --------------------------------
    print(
        {
            "event": "synthdog_stage_start",
            "stage": "data_copy",
            "run_id": run_id,
            "count_candidates": len(files),
            "truth_prefix": f"s3://{bucket}/{truth_prefix}/data/",
        }
    )
    t_stage = time.perf_counter()

    for path in files:
        files_seen += 1

        rel = path.relative_to(data_dir).as_posix()
        b = path.read_bytes()
        sha = _sha256_hex(b)
        size_bytes = path.stat().st_size
        content_type = _guess_content_type(path)

        key = f"{truth_prefix}/data/{rel}"
        client.upload_file(
            Filename=str(path),
            Bucket=bucket,
            Key=key,
            ExtraArgs={"ContentType": content_type},
        )

        if not exists(client, bucket, key):
            raise RuntimeError(
                f"Upload failed or not visible in MinIO: s3://{bucket}/{key}"
            )

        files_uploaded += 1
        manifest_rows.append(
            {
                "relative_path": rel,
                "filename": path.name,
                "sha256": sha,
                "size_bytes": size_bytes,
                "content_type": content_type,
            }
        )

    timings["data_copy"] = round(time.perf_counter() - t_stage, 6)

    # --------------------------------
    # Stage 3: manifest
    # --------------------------------
    print(
        {
            "event": "synthdog_stage_start",
            "stage": "manifest_write",
            "run_id": run_id,
            "manifest_prefix": f"s3://{bucket}/{manifest_prefix}",
        }
    )
    t_stage = time.perf_counter()

    manifest_json = _build_manifest_v1(run_id=run_id, rows=manifest_rows)
    manifest_key = f"{manifest_prefix}/manifest.v1.json"
    put_json(client, bucket, manifest_key, manifest_json)

    if not exists(client, bucket, manifest_key):
        raise RuntimeError(
            f"Write failed or not visible in MinIO: s3://{bucket}/{manifest_key}"
        )

    manifest_written = 1
    timings["manifest_write"] = round(time.perf_counter() - t_stage, 6)
    timings["total"] = round(time.perf_counter() - t0, 6)

    result = SynthdogTruthIngestResult(
        dataset="synthdog_en",
        run_id=run_id,
        limit_files=limit_files,
        files_seen=files_seen,
        files_uploaded=files_uploaded,
        dataset_info_written=dataset_info_written,
        manifest_written=manifest_written,
        timings=timings,
        paths={
            "truth_prefix": f"s3://{bucket}/{truth_prefix}",
            "dataset_info_key": f"s3://{bucket}/{dataset_info_key}",
            "manifest_key": f"s3://{bucket}/{manifest_key}",
        },
    )

    print(
        {
            "event": "synthdog_ingest_complete",
            "dataset": result.dataset,
            "run_id": result.run_id,
            "limit_files": result.limit_files,
            "counts": {
                "files_seen": result.files_seen,
                "files_uploaded": result.files_uploaded,
                "dataset_info_written": result.dataset_info_written,
                "manifest_written": result.manifest_written,
            },
            "timings": result.timings,
            "paths": result.paths,
        }
    )

    return result
