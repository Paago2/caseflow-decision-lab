from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from caseflow.repo.minio_s3 import make_minio_s3_client


def ingest_census_bg_to_minio(
    shapefile_path: Path,
    bucket: str = "lake",
    year: str = "2025",
    state: str = "VA",
):
    print({"event": "census_tiger_stage_start", "stage": "read_shapefile"})

    gdf = gpd.read_file(shapefile_path)

    print({"rows": len(gdf), "columns": list(gdf.columns)})

    output_local = Path(f"/tmp/bg_{year}_{state}.parquet")

    print({"event": "write_parquet", "path": str(output_local)})

    gdf.to_parquet(output_local)

    key = f"geo/silver/census_tiger/{year}/bg/state={state}/bg_{year}_{state}.parquet"

    client = make_minio_s3_client()

    print({"event": "upload_to_minio", "key": key})

    client.upload_file(str(output_local), bucket, key)

    print({"event": "census_tiger_ingest_complete", "bucket": bucket, "key": key})
