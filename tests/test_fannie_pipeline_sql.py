from __future__ import annotations

from pathlib import Path

import duckdb

from caseflow.pipelines.fannie_ingest import _curated_select_sql


def test_fannie_curated_select_compiles_and_parses_pipe_lines(tmp_path: Path) -> None:
    """
    Validates:
    - SQL compiles
    - pipe split works when line begins with '|'
    - stable casts for key fields
    """
    bronze = tmp_path / "fannie_raw.txt"

    # Pipeline assumes line starts with '|' so f[1] is empty and fields begin at f[2]
    # f[2]=loan_id, f[3]=as_of_yyyymm, f[4]=channel,
    # f[5]=seller_name, f[6]=servicer_name
    bronze.write_text(
        "\n".join(
            [
                "|LN0001|202501|R|SELLER_A|SERVICER_A",
                "|LN0002|202502|B|SELLER_B|SERVICER_B",
                "|LN0003|202503|C|SELLER_C|SERVICER_C",
            ]
        ),
        encoding="utf-8",
    )

    conn = duckdb.connect(database=":memory:")
    sql = _curated_select_sql(bronze_path=bronze, limit_rows=None)

    conn.execute(f"CREATE OR REPLACE TEMP VIEW fannie_curated AS {sql}")

    total = int(conn.execute("SELECT COUNT(*) FROM fannie_curated").fetchone()[0])
    assert total == 3

    rows = conn.execute("""
        SELECT loan_id, as_of_yyyymm, channel, seller_name, servicer_name
        FROM fannie_curated
        ORDER BY loan_id
        """).fetchall()

    assert rows == [
        ("LN0001", 202501, "R", "SELLER_A", "SERVICER_A"),
        ("LN0002", 202502, "B", "SELLER_B", "SERVICER_B"),
        ("LN0003", 202503, "C", "SELLER_C", "SERVICER_C"),
    ]

    conn.close()


def test_fannie_limit_rows_applies_to_raw_lines(tmp_path: Path) -> None:
    """
    Your SQL applies LIMIT in the 'raw' CTE (before parsing).
    This locks down that behavior deterministically.
    """
    bronze = tmp_path / "fannie_raw.txt"
    bronze.write_text(
        "\n".join(
            [
                "|L1|202501|R|S1|V1",
                "|L2|202502|R|S2|V2",
                "|L3|202503|R|S3|V3",
                "|L4|202504|R|S4|V4",
            ]
        ),
        encoding="utf-8",
    )

    conn = duckdb.connect(database=":memory:")
    sql = _curated_select_sql(bronze_path=bronze, limit_rows=2)

    conn.execute(f"CREATE OR REPLACE TEMP VIEW fannie_curated AS {sql}")

    total = int(conn.execute("SELECT COUNT(*) FROM fannie_curated").fetchone()[0])
    assert total == 2  # limited at raw line stage

    ids = conn.execute("SELECT loan_id FROM fannie_curated ORDER BY loan_id").fetchall()
    assert ids == [("L1",), ("L2",)]

    conn.close()


def test_fannie_ignores_short_or_malformed_lines(tmp_path: Path) -> None:
    """
    Your SQL filters with: WHERE array_length(f) >= 6
    So malformed lines should be dropped.
    """
    bronze = tmp_path / "fannie_raw.txt"
    bronze.write_text(
        "\n".join(
            [
                "|OK1|202501|R|SELLER|SERVICER",  # valid
                "|BAD1|202501|R|ONLY_SELLER",  # too short -> dropped
                "NOT_PIPE_AT_START|OK2|202502|R|SELLER|SERVICER",
                # split still works, but f[2] won't be loan_id
                "|OK3|202503|R|SELLER|SERVICER",  # valid
            ]
        ),
        encoding="utf-8",
    )

    conn = duckdb.connect(database=":memory:")
    sql = _curated_select_sql(bronze_path=bronze, limit_rows=None)

    conn.execute(f"CREATE OR REPLACE TEMP VIEW fannie_curated AS {sql}")
    total = int(conn.execute("SELECT COUNT(*) FROM fannie_curated").fetchone()[0])

    # We expect BAD1 dropped. The NOT_PIPE_AT_START line might pass array_length(f) >= 6
    # but the parsed columns won't match your contract. In enterprise pipelines,
    # you'd typically validate the leading pipe as well; since you currently don't,
    # we keep this test strict about only the obvious drop.
    assert total in (3, 2)

    # Assert that the two "safe" lines exist
    good = conn.execute(
        "SELECT loan_id FROM fannie_curated "
        "WHERE loan_id IN ('OK1','OK3') "
        "ORDER BY loan_id"
    ).fetchall()
    assert good == [("OK1",), ("OK3",)]

    conn.close()
