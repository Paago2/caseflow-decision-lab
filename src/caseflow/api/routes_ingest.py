from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from caseflow.core.audit import get_audit_sink
from caseflow.core.metrics import increment_metric, observe_ms_metric, set_gauge_metric
from caseflow.core.settings import get_settings
from caseflow.repo import ingestion_repo

router = APIRouter()
logger = logging.getLogger(__name__)


class IngestRawRequest(BaseModel):
    source_path: str = "/app/data/00_raw"
    limit: int | None = None
    dry_run: bool = False


def _resolve_source_path(source_path: str) -> Path:
    path = Path(source_path).resolve()
    if not path.exists() and source_path == "/app/data/00_raw":
        path = Path("./data/00_raw").resolve()
    return path


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def _ensure_bucket_exists(s3_client, bucket: str) -> None:
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError:
        s3_client.create_bucket(Bucket=bucket)


def _upload_files(
    *, files: list[Path], source_dir: Path, bucket: str, endpoint_url: str
) -> None:
    settings = get_settings()
    s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    _ensure_bucket_exists(s3_client, bucket)

    for file_path in files:
        key = f"00_raw/{file_path.relative_to(source_dir).as_posix()}"
        s3_client.upload_file(Filename=str(file_path), Bucket=bucket, Key=key)


@router.post("/ingest/raw")
def ingest_raw(payload: IngestRawRequest) -> JSONResponse:
    settings = get_settings()
    run_id = str(uuid4())
    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()

    source_dir = _resolve_source_path(payload.source_path)
    s3_prefix = "00_raw"

    ingestion_repo.create_run(
        run_id=run_id,
        status="started",
        started_at=started_at,
        source_path=str(source_dir),
        s3_bucket=settings.s3_bucket_raw,
        s3_prefix=s3_prefix,
    )
    increment_metric('ingestion_runs_total{status="started"}')

    try:
        get_audit_sink().emit_decision_event(
            {
                "event": "ingestion_run_started",
                "run_id": run_id,
                "source_path": str(source_dir),
                "s3_bucket": settings.s3_bucket_raw,
                "s3_prefix": s3_prefix,
                "dry_run": payload.dry_run,
                "timestamp": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    except Exception:
        logger.exception("ingestion_run_audit_start_failed", extra={"run_id": run_id})

    try:
        if not source_dir.exists() or not source_dir.is_dir():
            raise ValueError(f"source_path_not_found: {source_dir}")

        files = list(_iter_files(source_dir))
        if payload.limit is not None and payload.limit > 0:
            files = files[: payload.limit]

        total_bytes = 0
        sample_keys: list[str] = []
        for file_path in files:
            key = f"00_raw/{file_path.relative_to(source_dir).as_posix()}"
            total_bytes += file_path.stat().st_size
            if len(sample_keys) < 5:
                sample_keys.append(key)

        if not payload.dry_run and files:
            _upload_files(
                files=files,
                source_dir=source_dir,
                bucket=settings.s3_bucket_raw,
                endpoint_url=settings.s3_endpoint_url,
            )

        finished_at = datetime.now(timezone.utc)
        ingestion_repo.complete_run(
            run_id=run_id,
            finished_at=finished_at,
            file_count=len(files),
            total_bytes=total_bytes,
            sample_keys=sample_keys,
        )

        duration_seconds = time.perf_counter() - started_perf
        increment_metric('ingestion_runs_total{status="completed"}')
        observe_ms_metric("ingestion_duration_seconds", duration_seconds)
        set_gauge_metric("last_ingestion_file_count", float(len(files)))

        try:
            get_audit_sink().emit_decision_event(
                {
                    "event": "ingestion_run_completed",
                    "run_id": run_id,
                    "status": "completed",
                    "dry_run": payload.dry_run,
                    "file_count": len(files),
                    "total_bytes": total_bytes,
                    "sample_keys": sample_keys,
                    "timestamp": finished_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
        except Exception:
            logger.exception(
                "ingestion_run_audit_complete_failed", extra={"run_id": run_id}
            )

        return JSONResponse(
            status_code=200,
            content={
                "run_id": run_id,
                "status": "completed",
                "manifest": {
                    "file_count": len(files),
                    "total_bytes": total_bytes,
                    "sample_keys": sample_keys,
                    "source_path": str(source_dir),
                    "s3_bucket": settings.s3_bucket_raw,
                    "s3_prefix": s3_prefix,
                    "dry_run": payload.dry_run,
                },
            },
        )

    except Exception as exc:
        error = str(exc).strip() or "ingestion_failed"
        finished_at = datetime.now(timezone.utc)

        try:
            ingestion_repo.fail_run(run_id=run_id, finished_at=finished_at, error=error)
        except Exception:
            logger.exception(
                "ingestion_run_fail_persist_failed",
                extra={"run_id": run_id},
            )
        increment_metric('ingestion_runs_total{status="failed"}')

        try:
            get_audit_sink().emit_decision_event(
                {
                    "event": "ingestion_run_failed",
                    "run_id": run_id,
                    "status": "failed",
                    "error": error,
                    "timestamp": finished_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
        except Exception:
            logger.exception(
                "ingestion_run_audit_fail_failed",
                extra={"run_id": run_id},
            )
        return JSONResponse(
            status_code=500,
            content={
                "run_id": run_id,
                "status": "failed",
                "reason": error,
            },
        )
