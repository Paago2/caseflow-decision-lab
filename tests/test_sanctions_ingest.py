from pathlib import Path

import duckdb

from caseflow.pipelines.sanctions_ingest import _curated_select_sql


def test_sanctions_curated_select_compiles(tmp_path: Path) -> None:
    csv_path = tmp_path / "sanctions.csv"
    csv_path.write_text(
        "\n".join(
            [
                "name,country,program",
                "John Doe,US,TEST",
                "Jane Doe,UK,TEST2",
            ]
        ),
        encoding="utf-8",
    )

    conn = duckdb.connect(database=":memory:")
    sql = _curated_select_sql(csv_path, limit_rows=None)

    conn.execute(f"CREATE OR REPLACE TEMP VIEW sanctions_curated AS {sql}")
    total_rows = conn.execute("SELECT COUNT(*) FROM sanctions_curated").fetchone()[0]

    assert total_rows == 2
    conn.close()
