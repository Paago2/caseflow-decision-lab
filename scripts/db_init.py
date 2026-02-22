from __future__ import annotations

from caseflow.core.db import get_conn

DDL = """
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NULL,
    source_path TEXT NOT NULL,
    s3_bucket TEXT NOT NULL,
    s3_prefix TEXT NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0,
    total_bytes BIGINT NOT NULL DEFAULT 0,
    sample_keys_json TEXT NOT NULL DEFAULT '[]',
    error TEXT NULL
);
"""


def main() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
    print("db init complete: ingestion_runs table is ready")


if __name__ == "__main__":
    main()
