from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass
class HmdaIngestResult:
    year: int
    run_id: str
    mode: str
    limit_rows: int | None
    silver_rows: int
    silver_states: int
    gold_rows: int
    timings: dict[str, float]
    silver_file: str
    silver_partitioned_path: str
    gold_path: str


def _curated_select_sql(
    bronze_csv_path: Path, year: int, limit_rows: int | None = None
) -> str:
    """
    Build a canonical SELECT for HMDA CSVs.

    Enterprise rule:
      - DO NOT use sample_size=-1 (full-file inference is slow on huge CSVs).
      - Cast into stable canonical columns so downstream is deterministic.

    Supported input shapes:
      A) HMDA 2017 "labels" CSV columns (what you actually have):
         - as_of_year, respondent_id, state_abbr, county_code, census_tract_number,
           loan_amount_000s, applicant_income_000s, action_taken,
           applicant_ethnicity, applicant_race_1, applicant_sex

      B) Canonical-ish CSV columns (already standardized):
         - lei, activity_year, state_code, county_code, census_tract,
           loan_amount, income,
           action_taken, applicant_ethnicity_1, applicant_race_1, applicant_sex, ...
    """
    csv_path_sql = bronze_csv_path.as_posix().replace("'", "''")
    limit_clause = f" LIMIT {int(limit_rows)}" if limit_rows else ""

    # Detect columns cheaply (no sample_size=-1!)
    conn = duckdb.connect(database=":memory:")
    described = conn.execute(
        f"DESCRIBE SELECT * FROM read_csv_auto('{csv_path_sql}', header=true) LIMIT 1"
    ).fetchall()
    conn.close()
    cols = {row[0].lower() for row in described}

    # Branch: already-canonical vs 2017-labels
    has_activity_year = "activity_year" in cols
    has_as_of_year = "as_of_year" in cols

    if has_activity_year:
        # Already standardized-ish input
        return f"""
            SELECT
                CAST(lei AS VARCHAR)                     AS lei,
                CAST(activity_year AS INTEGER)           AS activity_year,
                CAST(state_code AS VARCHAR)              AS state_abbr,
                CAST(county_code AS VARCHAR)             AS county_code,
                CAST(census_tract AS VARCHAR)            AS census_tract,
                CAST(loan_amount AS DOUBLE)              AS loan_amount,
                CAST(income AS DOUBLE)                   AS income,
                CAST(action_taken AS INTEGER)            AS action_taken,
                CAST(applicant_ethnicity_1 AS INTEGER)   AS applicant_ethnicity_1,
                CAST(applicant_race_1 AS INTEGER)        AS applicant_race_1,
                CAST(applicant_sex AS INTEGER)           AS applicant_sex,

                CAST(derived_msa_md AS VARCHAR)          AS derived_msa_md,
                CAST(derived_loan_product_type AS VARCHAR)
                    AS derived_loan_product_type,
                CAST(derived_dwelling_category AS VARCHAR)
                    AS derived_dwelling_category,
                CAST(derived_race AS VARCHAR)             AS derived_race,
                CAST(derived_ethnicity AS VARCHAR)        AS derived_ethnicity,
                CAST(derived_sex AS VARCHAR)              AS derived_sex,

                CAST(interest_rate AS DOUBLE)            AS interest_rate,
                CAST(origination_charges AS DOUBLE)      AS origination_charges,
                CAST(property_value AS DOUBLE)           AS property_value,
                CAST(occupancy_type AS INTEGER)          AS occupancy_type,
                CAST(loan_term AS INTEGER)               AS loan_term,
                CAST(lien_status AS INTEGER)             AS lien_status
            FROM read_csv_auto('{csv_path_sql}', header=true)
            WHERE activity_year = {int(year)}
            {limit_clause}
        """

    if has_as_of_year:
        # HMDA 2017 labels input (fast + deterministic)
        return f"""
            SELECT
                CAST(respondent_id AS VARCHAR)        AS lei,
                CAST(as_of_year AS INTEGER)           AS activity_year,
                CAST(state_abbr AS VARCHAR)           AS state_abbr,
                CAST(county_code AS VARCHAR)          AS county_code,
                CAST(census_tract_number AS VARCHAR)  AS census_tract,
                CAST(loan_amount_000s AS DOUBLE)      AS loan_amount,
                CAST(applicant_income_000s AS DOUBLE) AS income,
                CAST(action_taken AS INTEGER)         AS action_taken,
                CAST(applicant_ethnicity AS INTEGER)  AS applicant_ethnicity_1,
                CAST(applicant_race_1 AS INTEGER)     AS applicant_race_1,
                CAST(applicant_sex AS INTEGER)        AS applicant_sex,

                -- Keep schema stable for downstream even if 2017 labels lacks these:
                NULL::VARCHAR AS derived_msa_md,
                NULL::VARCHAR AS derived_loan_product_type,
                NULL::VARCHAR AS derived_dwelling_category,
                NULL::VARCHAR AS derived_race,
                NULL::VARCHAR AS derived_ethnicity,
                NULL::VARCHAR AS derived_sex,

                NULL::DOUBLE  AS interest_rate,
                NULL::DOUBLE  AS origination_charges,
                NULL::DOUBLE  AS property_value,
                NULL::INTEGER AS occupancy_type,
                NULL::INTEGER AS loan_term,
                NULL::INTEGER AS lien_status
            FROM read_csv_auto('{csv_path_sql}', header=true)
            WHERE as_of_year = {int(year)}
            {limit_clause}
        """

    raise ValueError(
        "Unsupported HMDA CSV schema. Expected either {as_of_year,...} (2017 labels) "
        "or {activity_year,...} (standardized)."
    )


def ingest_hmda_2017_to_minio(
    bronze_csv_path: Path,
    bucket: str = "lake",
    year: int = 2017,
    limit_rows: int | None = None,
    *,
    mode: str = "skip",  # "skip" | "overwrite"
    run_id: str = "default",
) -> HmdaIngestResult:
    """
    Enterprise performance pattern:
      1) Materialize canonical curated parquet ONCE (CSV -> Parquet "cache").
      2) Partition from canonical parquet (fast).
      3) Gold aggregates from canonical parquet (fast).

    mode:
      - skip: do not overwrite existing files (uses OVERWRITE_OR_IGNORE where possible)
      - overwrite: overwrite outputs deterministically
    """
    if mode not in {"skip", "overwrite"}:
        raise ValueError("mode must be 'skip' or 'overwrite'")

    conn = duckdb.connect(database=":memory:")
    _configure_duckdb_for_minio(conn)

    curated_sql = _curated_select_sql(
        bronze_csv_path=bronze_csv_path, year=year, limit_rows=limit_rows
    )

    # Output paths
    silver_dir = f"s3://{bucket}/hmda/silver/{year}/run_id={run_id}/curated/"
    silver_file = f"{silver_dir}part-00000.parquet"

    silver_partitioned_path = (
        f"s3://{bucket}/hmda/silver/{year}/run_id={run_id}/curated_by_state/"
    )
    gold_path = (
        f"s3://{bucket}/hmda/gold/{year}/run_id={run_id}/state_kpis/state_kpis.parquet"
    )

    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    # -----------------------------
    # Stage 1: CSV -> canonical Parquet
    # -----------------------------
    print(
        {
            "event": "hmda_stage_start",
            "stage": "silver_materialize",
            "year": year,
            "run_id": run_id,
            "mode": mode,
            "limit_rows": limit_rows,
            "silver_file": silver_file,
        }
    )

    # COPY options
    silver_copy_opts = "FORMAT PARQUET, COMPRESSION ZSTD"
    if mode == "overwrite":
        silver_copy_opts += ", OVERWRITE TRUE"
    else:
        # If file exists, do NOT rewrite it
        # (DuckDB doesn't have a "skip if exists" for single-file COPY in all versions,
        #  but OVERWRITE_OR_IGNORE is supported for many COPY targets. We try it.)
        silver_copy_opts += ", OVERWRITE_OR_IGNORE TRUE"

    t_stage = time.perf_counter()
    conn.execute(f"COPY ({curated_sql}) TO '{silver_file}' ({silver_copy_opts});")
    timings["silver_write"] = round(time.perf_counter() - t_stage, 6)

    # IMPORTANT: downstream reads ONLY the canonical parquet (cache)
    conn.execute(
        "CREATE OR REPLACE TEMP VIEW hmda_curated AS "
        f"SELECT * FROM read_parquet('{silver_file}')"
    )

    silver_rows = conn.execute("SELECT COUNT(*) FROM hmda_curated").fetchone()[0]
    silver_states = conn.execute(
        "SELECT COUNT(DISTINCT state_abbr) "
        "FROM hmda_curated "
        "WHERE state_abbr IS NOT NULL"
    ).fetchone()[0]

    # -----------------------------
    # Stage 2: canonical -> partitioned
    # -----------------------------
    print(
        {
            "event": "hmda_stage_start",
            "stage": "silver_partition",
            "year": year,
            "run_id": run_id,
            "mode": mode,
            "silver_partitioned_path": silver_partitioned_path,
        }
    )

    part_copy_opts = "FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (state_abbr)"
    if mode == "overwrite":
        part_copy_opts += ", OVERWRITE TRUE"
    else:
        # This avoids the "Directory is not empty!" failure in skip mode.
        part_copy_opts += ", OVERWRITE_OR_IGNORE TRUE"

    t_stage = time.perf_counter()
    conn.execute(
        f"COPY hmda_curated TO '{silver_partitioned_path}' ({part_copy_opts});"
    )
    timings["partitioned_write"] = round(time.perf_counter() - t_stage, 6)

    # -----------------------------
    # Stage 3: gold KPIs from canonical parquet
    # -----------------------------
    print(
        {
            "event": "hmda_stage_start",
            "stage": "gold_kpis",
            "year": year,
            "run_id": run_id,
            "mode": mode,
            "gold_path": gold_path,
        }
    )

    gold_copy_opts = "FORMAT PARQUET, COMPRESSION ZSTD"
    if mode == "overwrite":
        gold_copy_opts += ", OVERWRITE TRUE"
    else:
        gold_copy_opts += ", OVERWRITE_OR_IGNORE TRUE"

    t_stage = time.perf_counter()
    conn.execute(f"""
        COPY (
            SELECT
                state_abbr,
                COUNT(*)::BIGINT AS applications,
                SUM(CASE WHEN action_taken = 1 THEN 1 ELSE 0 END)::BIGINT AS approvals,
                AVG(loan_amount)::DOUBLE AS avg_loan_amount,
                AVG(income)::DOUBLE AS avg_income,
                AVG(interest_rate)::DOUBLE AS avg_interest_rate
            FROM hmda_curated
            WHERE state_abbr IS NOT NULL
            GROUP BY 1
            ORDER BY 1
        ) TO '{gold_path}' ({gold_copy_opts});
        """)
    timings["gold_write"] = round(time.perf_counter() - t_stage, 6)

    gold_rows = conn.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT state_abbr "
        "FROM hmda_curated "
        "WHERE state_abbr IS NOT NULL "
        "GROUP BY 1"
        ")"
    ).fetchone()[0]

    timings["total"] = round(time.perf_counter() - t0, 6)

    result = HmdaIngestResult(
        year=year,
        run_id=run_id,
        mode=mode,
        limit_rows=limit_rows,
        silver_rows=int(silver_rows),
        silver_states=int(silver_states),
        gold_rows=int(gold_rows),
        timings=timings,
        silver_file=silver_file,
        silver_partitioned_path=silver_partitioned_path,
        gold_path=gold_path,
    )

    print(
        {
            "event": "hmda_ingest_complete",
            "year": year,
            "run_id": run_id,
            "limit_rows": limit_rows,
            "row_count": int(silver_rows),
            "state_count": int(gold_rows),
            "counts": {
                "silver_rows": int(silver_rows),
                "silver_states": int(silver_states),
                "gold_rows": int(gold_rows),
            },
            "timings": result.timings,
            "paths": {
                "silver_file": silver_file,
                "silver_partitioned_path": silver_partitioned_path,
                "gold_path": gold_path,
            },
        }
    )

    conn.close()
    return result


def _configure_duckdb_for_minio(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")

    # MinIO is S3-compatible; keep path-style addressing.
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
