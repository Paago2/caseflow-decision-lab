from __future__ import annotations

import os
import time
from dataclasses import dataclass

import duckdb


@dataclass
class FreddieIngestResult:
    dataset_id: str
    run_id: str
    limit_rows: int | None
    silver_loans_rows: int
    silver_perf_rows: int
    timings: dict[str, float]
    paths: dict[str, str]


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
        "SET s3_secret_access_key='"
        f"{os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin')}';"
    )


def _read_freddie_raw_sql(bronze: str) -> str:
    b = str(bronze).replace("'", "''")

    # CRT files vary by deal/series; some rows are wider than others.
    # Oversize the schema so we never fail on "Found: 81" type issues.
    N = 200
    cols = ", ".join([f"c{i}: VARCHAR" for i in range(N)])

    return f"""
        SELECT * FROM read_csv(
            '{b}',
            delim='|',
            header=false,
            auto_detect=false,
            null_padding=true,
            strict_mode=false,
            filename=true,
            columns={{ {cols} }}
        )
    """


def _curated_loans_20_sql(bronze: str, limit_rows: int | None) -> str:
    limit_clause = f" LIMIT {int(limit_rows)}" if limit_rows else ""
    raw_sql = _read_freddie_raw_sql(bronze)

    return f"""
        SELECT
            TRIM(c1)                                  AS loan_id,
            TRIM(c3)                                  AS product_type,

            TRIM(c12)                                 AS seller,
            TRIM(c13)                                 AS state,
            TRIM(c14)                                 AS zip3,
            TRIM(c15)                                 AS msa,

            TRY_CAST(TRIM(c16) AS INTEGER)             AS orig_yyyymm,
            TRY_CAST(TRIM(c17) AS INTEGER)             AS first_pay_yyyymm,
            TRY_CAST(TRIM(c18) AS INTEGER)             AS original_term_months,

            TRY_CAST(TRIM(c19) AS DOUBLE)              AS note_rate,

            TRY_CAST(TRIM(c20) AS DOUBLE)              AS orig_upb,
            TRY_CAST(TRIM(c21) AS DOUBLE)              AS upb_at_cutoff,

            TRY_CAST(TRIM(c30) AS INTEGER)             AS borrower_credit_score,

            -- Traceability / debugging
            TRIM(c0)                                   AS record_type,
            filename                                   AS source_file
        FROM ({raw_sql})
        WHERE TRIM(c0) = '20'
        {limit_clause}
    """


def _curated_perf_50_sql(bronze: str, limit_rows: int | None) -> str:
    limit_clause = f" LIMIT {int(limit_rows)}" if limit_rows else ""
    raw_sql = _read_freddie_raw_sql(bronze)

    return f"""
        SELECT
            TRIM(c1)                                  AS loan_id,
            TRY_CAST(TRIM(c2) AS INTEGER)              AS as_of_yyyymm,

            TRIM(c3)                                  AS seller,

            TRY_CAST(TRIM(c4) AS DOUBLE)               AS servicing_fee_rate,
            TRY_CAST(TRIM(c5) AS DOUBLE)               AS note_rate,

            TRY_CAST(TRIM(c7) AS DOUBLE)               AS current_upb_est,

            TRIM(c15)                                 AS delinquency_status_code,
            TRY_CAST(TRIM(c16) AS INTEGER)             AS loan_age_months,

            -- Traceability / debugging
            TRIM(c0)                                   AS record_type,
            filename                                   AS source_file
        FROM ({raw_sql})
        WHERE TRIM(c0) = '50'
        {limit_clause}
    """


def ingest_freddie_crt_lld_to_minio(
    bronze: str,
    bucket: str,
    dataset_id: str,
    run_id: str,
    limit_rows: int | None,
) -> FreddieIngestResult:
    conn = duckdb.connect(database=":memory:")
    _configure_duckdb_for_minio(conn)

    silver_loans_file = f"s3://{bucket}/freddie/silver/{dataset_id}/run_id={run_id}/loans/part-00000.parquet"
    silver_perf_file = f"s3://{bucket}/freddie/silver/{dataset_id}/run_id={run_id}/perf/part-00000.parquet"

    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    # -----------------------------
    # Silver: loans (20)
    # -----------------------------
    loans_sql = _curated_loans_20_sql(bronze, limit_rows=limit_rows)
    print(
        {
            "event": "freddie_stage_start",
            "stage": "silver_loans_20",
            "dataset_id": dataset_id,
            "run_id": run_id,
            "limit_rows": limit_rows,
            "silver_file": silver_loans_file,
            "bronze": bronze,
        }
    )
    t = time.perf_counter()
    conn.execute(
        f"COPY ({loans_sql}) TO '{silver_loans_file}' "
        "(FORMAT PARQUET, COMPRESSION ZSTD);"
    )
    timings["silver_loans_write"] = round(time.perf_counter() - t, 6)

    # -----------------------------
    # Silver: performance (50)
    # -----------------------------
    perf_sql = _curated_perf_50_sql(bronze, limit_rows=limit_rows)
    print(
        {
            "event": "freddie_stage_start",
            "stage": "silver_perf_50",
            "dataset_id": dataset_id,
            "run_id": run_id,
            "limit_rows": limit_rows,
            "silver_file": silver_perf_file,
            "bronze": bronze,
        }
    )
    t = time.perf_counter()
    conn.execute(
        f"COPY ({perf_sql}) TO '{silver_perf_file}' (FORMAT PARQUET, COMPRESSION ZSTD);"
    )
    timings["silver_perf_write"] = round(time.perf_counter() - t, 6)

    # Counts (from parquet cache)
    conn.execute(
        "CREATE OR REPLACE TEMP VIEW freddie_loans AS "
        f"SELECT * FROM read_parquet('{silver_loans_file}')"
    )
    conn.execute(
        "CREATE OR REPLACE TEMP VIEW freddie_perf AS "
        f"SELECT * FROM read_parquet('{silver_perf_file}')"
    )

    loans_rows = int(conn.execute("SELECT COUNT(*) FROM freddie_loans").fetchone()[0])
    perf_rows = int(conn.execute("SELECT COUNT(*) FROM freddie_perf").fetchone()[0])

    timings["total"] = round(time.perf_counter() - t0, 6)

    result = FreddieIngestResult(
        dataset_id=dataset_id,
        run_id=run_id,
        limit_rows=limit_rows,
        silver_loans_rows=loans_rows,
        silver_perf_rows=perf_rows,
        timings=timings,
        paths={
            "silver_loans_file": silver_loans_file,
            "silver_perf_file": silver_perf_file,
        },
    )

    print(
        {
            "event": "freddie_ingest_complete",
            "dataset_id": dataset_id,
            "run_id": run_id,
            "limit_rows": limit_rows,
            "counts": {"silver_loans_rows": loans_rows, "silver_perf_rows": perf_rows},
            "timings": result.timings,
            "paths": result.paths,
        }
    )

    conn.close()
    return result
