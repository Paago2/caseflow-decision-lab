from pathlib import Path

import duckdb

from caseflow.pipelines.lending_club_ingest import _curated_select_sql


def test_lending_club_curated_select_compiles(tmp_path: Path) -> None:
    csv_path = tmp_path / "lending_club.csv"
    csv_path.write_text(
        "\n".join(
            [
                "loan_amnt,term,int_rate,grade,annual_inc,loan_status",
                "10000,36 months,10.65,A,50000,Fully Paid",
                "20000,60 months,13.49,B,80000,Charged Off",
            ]
        ),
        encoding="utf-8",
    )

    conn = duckdb.connect(database=":memory:")
    sql = _curated_select_sql(csv_path, limit_rows=None)

    conn.execute(f"CREATE OR REPLACE TEMP VIEW lending_club_curated AS {sql}")
    total_rows = conn.execute("SELECT COUNT(*) FROM lending_club_curated").fetchone()[0]

    assert total_rows == 2
    conn.close()
