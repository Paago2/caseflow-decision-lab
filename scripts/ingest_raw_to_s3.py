from __future__ import annotations

import argparse
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from caseflow.core.settings import get_settings


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def _ensure_bucket_exists(s3_client, bucket: str) -> None:
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError:
        s3_client.create_bucket(Bucket=bucket)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload local ./data/00_raw files into configured S3 raw bucket"
    )
    parser.add_argument("--source-dir", default="/app/data/00_raw")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists() and args.source_dir == "/app/data/00_raw":
        source_dir = Path("./data/00_raw").resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        raise SystemExit(
            f"source directory does not exist or is not a dir: {source_dir}"
        )

    settings = get_settings()

    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )

    if not args.dry_run:
        _ensure_bucket_exists(s3_client, settings.s3_bucket_raw)

    files = list(_iter_files(source_dir))
    if args.limit > 0:
        files = files[: args.limit]

    uploaded = 0
    total_bytes = 0
    keys: list[str] = []

    for file_path in files:
        relative = file_path.relative_to(source_dir).as_posix()
        key = f"00_raw/{relative}"
        size = file_path.stat().st_size

        if not args.dry_run:
            s3_client.upload_file(
                Filename=str(file_path),
                Bucket=settings.s3_bucket_raw,
                Key=key,
            )

        uploaded += 1
        total_bytes += size
        if len(keys) < 5:
            keys.append(key)

    mode = "dry-run" if args.dry_run else "upload"
    print(
        f"{mode} complete: files={uploaded} bytes={total_bytes} "
        f"bucket={settings.s3_bucket_raw}"
    )
    if keys:
        print("sample keys:")
        for key in keys:
            print(f"- {key}")


if __name__ == "__main__":
    main()
