from __future__ import annotations

import json
import os
from typing import Any

import boto3
from botocore.client import Config


def _endpoint_url() -> str:
    # You pass MINIO_S3_ENDPOINT like "caseflow-decision-lab-minio-1:9000"
    ep = os.getenv("MINIO_S3_ENDPOINT", "minio:9000").strip()
    if ep.startswith("http://") or ep.startswith("https://"):
        return ep
    return f"http://{ep}"


def make_minio_s3_client():
    access = os.getenv("MINIO_ROOT_USER", "minioadmin")
    secret = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    return boto3.client(
        "s3",
        endpoint_url=_endpoint_url(),
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def put_json(client, bucket: str, key: str, obj: dict[str, Any]) -> None:
    body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        Bucket=bucket,
        Key=key.lstrip("/"),
        Body=body,
        ContentType="application/json",
    )


def exists(client, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key.lstrip("/"))
        return True
    except Exception:
        return False
