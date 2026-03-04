from __future__ import annotations

import argparse

from caseflow.repo.minio_s3 import make_minio_s3_client


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", default="lake")
    p.add_argument("--prefix", required=True, help="S3 prefix to list")
    p.add_argument("--limit", type=int, default=80)
    args = p.parse_args()

    client = make_minio_s3_client()
    bucket = str(args.bucket)
    prefix = str(args.prefix).lstrip("/")
    limit = int(args.limit)

    printed = 0
    token = None

    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token

        resp = client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            print(obj["Key"])
            printed += 1
            if printed >= limit:
                return

        if not resp.get("IsTruncated"):
            return
        token = resp.get("NextContinuationToken")


if __name__ == "__main__":
    main()
