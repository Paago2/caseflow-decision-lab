import argparse
from pathlib import Path

from caseflow.pipelines.census_tiger_ingest import ingest_census_bg_to_minio


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--shapefile", required=True)
    parser.add_argument("--bucket", default="lake")
    parser.add_argument("--year", default="2025")
    parser.add_argument("--state", default="VA")

    args = parser.parse_args()

    ingest_census_bg_to_minio(
        shapefile_path=Path(args.shapefile),
        bucket=args.bucket,
        year=args.year,
        state=args.state,
    )


if __name__ == "__main__":
    main()
