from __future__ import annotations

from pathlib import Path

import duckdb

from caseflow.pipelines.freddie_ingest import (
    _curated_loans_20_sql,
    _curated_perf_50_sql,
)


def _row(cols: list[str], N: int = 200) -> str:
    """
    Freddie reader oversizes schema to N columns (c0..c199).
    We only need to supply the first len(cols); remaining columns may be empty.
    """
    if len(cols) > N:
        raise ValueError("too many cols for test row")
    padded = cols + [""] * (N - len(cols))
    return "|".join(padded)


def test_freddie_curated_sql_compiles_and_counts_are_deterministic(
    tmp_path: Path,
) -> None:
    """
    Validates:
    - SQL compiles
    - Filters record_type correctly (20 for loans, 50 for perf)
    - Produces deterministic row counts
    """
    # Minimal fields used by your SQL:
    # c0=record_type, c1=loan_id, c2=as_of_yyyymm (perf),
    # c3=product_type/seller (loans uses c3 product_type; perf uses c3 seller),
    # loans: c12 seller, c13 state, c14 zip3, c15 msa, c16.. etc
    # perf:  c4 servicing_fee_rate, c5 note_rate, c7 current_upb_est,
    # c15 delinquency_status_code, c16 loan_age_months

    lines = [
        # record type 20 (loan)
        _row(
            [
                "20",  # c0 record_type
                "L0001",  # c1 loan_id
                "",  # c2
                "Fixed",  # c3 product_type
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",  # c4..c11
                "SELLER_A",  # c12 seller
                "CA",  # c13 state
                "123",  # c14 zip3
                "99999",  # c15 msa
                "201701",  # c16 orig_yyyymm
                "201703",  # c17 first_pay_yyyymm
                "360",  # c18 original_term_months
                "4.5",  # c19 note_rate
                "250000",  # c20 orig_upb
                "240000",  # c21 upb_at_cutoff
                "",
                "",
                "",
                "",
                "",
                "",
                "",  # c22..c28
                "720",  # c30 borrower_credit_score (note c29 exists; keep empty)
            ]
        ),
        _row(
            [
                "20",
                "L0002",
                "",
                "ARM",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "SELLER_B",
                "NY",
                "100",
                "11111",
                "201702",
                "201704",
                "180",
                "5.25",
                "150000",
                "145000",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",  # c29
                "680",  # c30
            ]
        ),
        # record type 50 (performance)
        _row(
            [
                "50",  # c0
                "L0001",  # c1 loan_id
                "201812",  # c2 as_of_yyyymm
                "SELLER_A",  # c3 seller
                "0.25",  # c4 servicing_fee_rate
                "4.5",  # c5 note_rate
                "",  # c6
                "230000",  # c7 current_upb_est
                "",
                "",
                "",
                "",
                "",
                "",  # c8..c14
                "0",  # c15 delinquency_status_code
                "24",  # c16 loan_age_months
            ]
        ),
        _row(
            [
                "50",
                "L0002",
                "201901",
                "SELLER_B",
                "0.30",
                "5.25",
                "",
                "140000",
                "",
                "",
                "",
                "",
                "",
                "",
                "1",
                "12",
            ]
        ),
        # a row of a different record type to prove filter works
        _row(["10", "IGNORED_LOAN", "", "NA"]),
    ]

    txt = tmp_path / "freddie_lld.txt"
    txt.write_text("\n".join(lines), encoding="utf-8")

    conn = duckdb.connect(database=":memory:")

    loans_sql = _curated_loans_20_sql(str(txt), limit_rows=None)
    perf_sql = _curated_perf_50_sql(str(txt), limit_rows=None)

    # Compile + count
    loans_count = int(conn.execute(f"SELECT COUNT(*) FROM ({loans_sql})").fetchone()[0])
    perf_count = int(conn.execute(f"SELECT COUNT(*) FROM ({perf_sql})").fetchone()[0])

    assert loans_count == 2
    assert perf_count == 2

    # basic schema expectations (just a few key cols)
    loans_cols = [
        r[0] for r in conn.execute(f"DESCRIBE SELECT * FROM ({loans_sql})").fetchall()
    ]
    perf_cols = [
        r[0] for r in conn.execute(f"DESCRIBE SELECT * FROM ({perf_sql})").fetchall()
    ]

    assert "loan_id" in loans_cols
    assert "product_type" in loans_cols
    assert "source_file" in loans_cols

    assert "loan_id" in perf_cols
    assert "as_of_yyyymm" in perf_cols
    assert "source_file" in perf_cols

    conn.close()


def test_freddie_limit_rows_applies_per_select(tmp_path: Path) -> None:
    """
    Your implementation applies LIMIT in each SELECT separately.
    This test locks that behavior down.
    """
    lines = []
    # 3 loans rows (20), 3 perf rows (50)
    for i in range(3):
        lines.append(_row(["20", f"L{i}", "", "Fixed"]))
    for i in range(3):
        lines.append(
            _row(
                [
                    "50",
                    f"L{i}",
                    "201801",
                    "SELLER",
                    "0.25",
                    "4.5",
                    "",
                    "100000",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "0",
                    "1",
                ]
            )
        )

    txt = tmp_path / "freddie_lld.txt"
    txt.write_text("\n".join(lines), encoding="utf-8")

    conn = duckdb.connect(database=":memory:")

    loans_sql = _curated_loans_20_sql(str(txt), limit_rows=2)
    perf_sql = _curated_perf_50_sql(str(txt), limit_rows=1)

    loans_count = int(conn.execute(f"SELECT COUNT(*) FROM ({loans_sql})").fetchone()[0])
    perf_count = int(conn.execute(f"SELECT COUNT(*) FROM ({perf_sql})").fetchone()[0])

    assert loans_count == 2
    assert perf_count == 1

    conn.close()
