from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from caseflow.core.db import get_conn


def create_run(
    *,
    run_id: str,
    status: str,
    started_at: datetime,
    source_path: str,
    s3_bucket: str,
    s3_prefix: str,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_runs (
                    id,
                    status,
                    started_at,
                    source_path,
                    s3_bucket,
                    s3_prefix,
                    file_count,
                    total_bytes,
                    sample_keys_json,
                    error
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    status,
                    started_at,
                    source_path,
                    s3_bucket,
                    s3_prefix,
                    0,
                    0,
                    "[]",
                    None,
                ),
            )


def complete_run(
    *,
    run_id: str,
    finished_at: datetime,
    file_count: int,
    total_bytes: int,
    sample_keys: list[str],
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_runs
                SET
                    status = %s,
                    finished_at = %s,
                    file_count = %s,
                    total_bytes = %s,
                    sample_keys_json = %s,
                    error = %s
                WHERE id = %s
                """,
                (
                    "completed",
                    finished_at,
                    file_count,
                    total_bytes,
                    json.dumps(sample_keys, separators=(",", ":")),
                    None,
                    run_id,
                ),
            )


def fail_run(*, run_id: str, finished_at: datetime, error: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_runs
                SET
                    status = %s,
                    finished_at = %s,
                    error = %s
                WHERE id = %s
                """,
                ("failed", finished_at, error, run_id),
            )


def get_run(run_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    status,
                    started_at,
                    finished_at,
                    source_path,
                    s3_bucket,
                    s3_prefix,
                    file_count,
                    total_bytes,
                    sample_keys_json,
                    error
                FROM ingestion_runs
                WHERE id = %s
                """,
                (run_id,),
            )
            row = cur.fetchone()

    if row is None:
        return None

    sample_keys: list[str]
    try:
        sample_keys = json.loads(row[9]) if row[9] else []
    except json.JSONDecodeError:
        sample_keys = []

    return {
        "id": row[0],
        "status": row[1],
        "started_at": row[2],
        "finished_at": row[3],
        "source_path": row[4],
        "s3_bucket": row[5],
        "s3_prefix": row[6],
        "file_count": row[7],
        "total_bytes": row[8],
        "sample_keys": sample_keys,
        "error": row[10],
    }
