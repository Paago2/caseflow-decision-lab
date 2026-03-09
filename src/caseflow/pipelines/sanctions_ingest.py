from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass
class SanctionsIngestResult:
    dataset_name: str
    run_id: str
    limit_rows: int | None
    silver_rows: int
    silver_file: str
    timings: dict[str, float]


def _configure_duckdb_for_minio(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")

    conn.execute("SET s3_region='us-east-1';")
    conn.execute("SET s3_url_style='path';")
    conn.execute("SET s3_use_ssl=false;")

    conn.execute(f"SET s3_endpoint='{os.getenv('MINIO_S3_ENDPOINT', 'minio:9000')}';")
    conn.execute(
        f"SET s3_access_key_id='{os.getenv('MINIO_ROOT_USER', 'minioadmin')}';"
    )
    conn.execute(
        f"SET s3_secret_access_key='{os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin')}';"
    )


def _curated_select_sql(
    bronze_csv_path: Path,
    limit_rows: int | None = None,
) -> str:
    """
    Read sanctions CSV files robustly.

    Government CSV files often have:
    - messy quoting
    - inconsistent rows
    - extra commas

    So we disable strict parsing and ignore bad rows.
    """

    csv_path_sql = bronze_csv_path.as_posix().replace("'", "''")
    limit_clause = f" LIMIT {int(limit_rows)}" if limit_rows else ""

    return f"""
        SELECT *
        FROM read_csv(
            '{csv_path_sql}',
            header=true,
            delim=',',
            strict_mode=false,
            ignore_errors=true,
            null_padding=true
        )
        {limit_clause}
    """


def ingest_sanctions_csv_to_minio(
    *,
    bronze_csv_path: Path,
    bucket: str,
    category: str,
    dataset_name: str,
    run_id: str,
    limit_rows: int | None,
) -> SanctionsIngestResult:
    conn = duckdb.connect(database=":memory:")

    _configure_duckdb_for_minio(conn)

    curated_sql = _curated_select_sql(
        bronze_csv_path=bronze_csv_path,
        limit_rows=limit_rows,
    )

    silver_dir = (
        f"s3://{bucket}/compliance/silver/{category}/{dataset_name}/run_id={run_id}/"
    )

    silver_file = f"{silver_dir}part-00000.parquet"

    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    print(
        {
            "event": "sanctions_stage_start",
            "stage": "silver_materialize",
            "category": category,
            "dataset_name": dataset_name,
            "run_id": run_id,
            "limit_rows": limit_rows,
            "silver_file": silver_file,
        }
    )

    t_stage = time.perf_counter()

    conn.execute(
        f"COPY ({curated_sql}) TO '{silver_file}' "
        "(FORMAT PARQUET, COMPRESSION ZSTD);"
    )

    timings["silver_write"] = round(time.perf_counter() - t_stage, 6)

    conn.execute(
        "CREATE OR REPLACE TEMP VIEW sanctions_silver AS "
        f"SELECT * FROM read_parquet('{silver_file}')"
    )

    silver_rows = int(
        conn.execute("SELECT COUNT(*) FROM sanctions_silver").fetchone()[0]
    )

    timings["total"] = round(time.perf_counter() - t0, 6)

    result = SanctionsIngestResult(
        dataset_name=dataset_name,
        run_id=run_id,
        limit_rows=limit_rows,
        silver_rows=silver_rows,
        silver_file=silver_file,
        timings=timings,
    )

    print(
        {
            "event": "sanctions_ingest_complete",
            "category": category,
            "dataset_name": dataset_name,
            "run_id": run_id,
            "limit_rows": limit_rows,
            "counts": {"silver_rows": silver_rows},
            "timings": result.timings,
            "paths": {"silver_file": silver_file},
        }
    )

    conn.close()

    return result
