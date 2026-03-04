from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass
class FannieIngestResult:
    dataset_id: str
    run_id: str
    limit_rows: int | None
    silver_rows: int
    timings: dict[str, float]
    silver_file: str


def _curated_select_sql(bronze_path: Path, limit_rows: int | None) -> str:
    """
    Enterprise-stable parse:
      - Read each row as a raw line (single VARCHAR)
      - Split by pipe into fields
      - Select exact field positions
      - Cast deterministically
    """
    p = bronze_path.as_posix().replace("'", "''")
    limit_clause = (
        f" LIMIT {int(limit_rows)}" if limit_rows and int(limit_rows) > 0 else ""
    )

    return f"""
        WITH raw AS (
            SELECT
                column0 AS line
            FROM read_csv(
                '{p}',
                delim='\\n',
                header=false,
                columns={{'column0':'VARCHAR'}}
            )
            {limit_clause}
        ),
        parsed AS (
            SELECT
                string_split(line, '|') AS f
            FROM raw
        )
        SELECT
            -- Since the line starts with '|', f[1] is empty
            CAST(f[2] AS VARCHAR)  AS loan_id,
            CAST(f[3] AS INTEGER)  AS as_of_yyyymm,
            CAST(f[4] AS VARCHAR)  AS channel,
            CAST(f[5] AS VARCHAR)  AS seller_name,
            CAST(f[6] AS VARCHAR)  AS servicer_name
        FROM parsed
        WHERE array_length(f) >= 6
    """


def ingest_fannie_loan_performance_to_minio(
    bronze_path: Path,
    bucket: str = "lake",
    dataset_id: str = "2025Q1",
    run_id: str = "sample",
    limit_rows: int | None = None,
) -> FannieIngestResult:
    """
    Enterprise pattern:
      1) CSV -> curated Parquet ONCE (silver cache)
      2) downstream reads use the parquet, not the CSV
    """
    conn = duckdb.connect(database=":memory:")
    _configure_duckdb_for_minio(conn)

    curated_sql = _curated_select_sql(bronze_path=bronze_path, limit_rows=limit_rows)

    silver_dir = f"s3://{bucket}/fannie/silver/{dataset_id}/run_id={run_id}/curated/"
    silver_file = f"{silver_dir}part-00000.parquet"

    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    print(
        {
            "event": "fannie_stage_start",
            "stage": "silver_materialize",
            "dataset_id": dataset_id,
            "run_id": run_id,
            "limit_rows": limit_rows,
            "silver_file": silver_file,
        }
    )

    t_stage = time.perf_counter()
    conn.execute(
        f"COPY ({curated_sql}) TO '{silver_file}' (FORMAT PARQUET, COMPRESSION ZSTD);"
    )
    timings["silver_write"] = round(time.perf_counter() - t_stage, 6)

    # Validate counts without touching CSV again
    conn.execute(
        "CREATE OR REPLACE TEMP VIEW fannie_silver AS "
        f"SELECT * FROM read_parquet('{silver_file}')"
    )
    silver_rows = int(conn.execute("SELECT COUNT(*) FROM fannie_silver").fetchone()[0])

    timings["total"] = round(time.perf_counter() - t0, 6)

    print(
        {
            "event": "fannie_ingest_complete",
            "dataset_id": dataset_id,
            "run_id": run_id,
            "limit_rows": limit_rows,
            "counts": {"silver_rows": silver_rows},
            "timings": timings,
            "paths": {"silver_file": silver_file},
        }
    )

    conn.close()
    return FannieIngestResult(
        dataset_id=dataset_id,
        run_id=run_id,
        limit_rows=limit_rows,
        silver_rows=silver_rows,
        timings=timings,
        silver_file=silver_file,
    )


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
