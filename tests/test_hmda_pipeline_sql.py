from pathlib import Path

import duckdb

from caseflow.pipelines.hmda_ingest import _curated_select_sql


def test_hmda_2017_curated_select_and_groupby_without_minio(tmp_path: Path) -> None:
    csv_path = tmp_path / "hmda_2017_tiny.csv"
    csv_path.write_text(
        "\n".join(
            [
                "as_of_year,agency_abbr,loan_type,property_type,loan_purpose,owner_occupancy,loan_amount_000s,action_taken,applicant_income_000s,county_name,state_abbr",
                "2017,CFPB,1,1,1,1,100,1,80,Los Angeles,CA",
                "2017,CFPB,1,1,1,1,200,3,120,Los Angeles,CA",
                "2017,CFPB,2,2,2,2,150,1,90,Kings,NY",
            ]
        ),
        encoding="utf-8",
    )

    conn = duckdb.connect(database=":memory:")
    curated_sql = f"""
        SELECT
            CAST(as_of_year AS INTEGER) AS as_of_year,
            CAST(agency_abbr AS VARCHAR) AS agency_abbr,
            CAST(loan_type AS INTEGER) AS loan_type,
            CAST(property_type AS INTEGER) AS property_type,
            CAST(loan_purpose AS INTEGER) AS loan_purpose,
            CAST(owner_occupancy AS INTEGER) AS owner_occupancy,
            CAST(loan_amount_000s AS DOUBLE) AS loan_amount_000s,
            CAST(action_taken AS INTEGER) AS action_taken,
            CAST(applicant_income_000s AS DOUBLE) AS applicant_income_000s,
            CAST(county_name AS VARCHAR) AS county_name,
            CAST(state_abbr AS VARCHAR) AS state_abbr
        FROM read_csv_auto('{csv_path.as_posix()}', header=true, sample_size=-1)
    """
    conn.execute(f"CREATE OR REPLACE TEMP VIEW hmda_curated AS {curated_sql}")

    total_rows = conn.execute("SELECT COUNT(*) FROM hmda_curated").fetchone()[0]
    assert total_rows == 3

    grouped = conn.execute("""
        SELECT
            state_abbr,
            COUNT(*) AS applications,
            SUM(CASE WHEN action_taken = 1 THEN 1 ELSE 0 END) AS approvals
        FROM hmda_curated
        GROUP BY 1
        ORDER BY 1
        """).fetchall()
    assert grouped == [("CA", 2, 1), ("NY", 1, 1)]
    conn.close()


def test_curated_select_compiles_and_state_kpis_are_deterministic(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "hmda_tiny.csv"
    csv_path.write_text(
        "\n".join(
            [
                "lei,activity_year,state_code,county_code,census_tract,loan_amount,income,action_taken,applicant_ethnicity_1,applicant_race_1,applicant_sex,derived_msa_md,derived_loan_product_type,derived_dwelling_category,derived_race,derived_ethnicity,derived_sex,interest_rate,origination_charges,property_value,occupancy_type,loan_term,lien_status",
                "L1,2017,CA,001,000100,100000,80,1,1,5,1,11111,Conventional,Single,RaceA,EthA,SexA,4.5,1000,400000,1,360,1",
                "L2,2017,CA,001,000200,200000,120,3,2,3,2,11111,FHA,Single,RaceB,EthB,SexB,5.0,1200,500000,1,360,1",
                "L3,2017,NY,005,000300,150000,90,1,1,1,1,22222,VA,Multi,RaceC,EthC,SexC,4.0,900,450000,2,180,2",
            ]
        ),
        encoding="utf-8",
    )

    conn = duckdb.connect(database=":memory:")
    curated_sql = _curated_select_sql(csv_path, year=2017)

    conn.execute(f"CREATE OR REPLACE TEMP VIEW hmda_curated AS {curated_sql}")

    total_rows = conn.execute("SELECT COUNT(*) FROM hmda_curated").fetchone()[0]
    assert total_rows == 3

    kpis = conn.execute("""
        SELECT
            state_abbr,
            COUNT(*) AS applications,
            SUM(CASE WHEN action_taken = 1 THEN 1 ELSE 0 END) AS approvals
        FROM hmda_curated
        WHERE state_abbr IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """).fetchall()

    assert kpis == [("CA", 2, 1), ("NY", 1, 1)]
    conn.close()
