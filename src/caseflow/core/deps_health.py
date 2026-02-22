from __future__ import annotations

import socket
from urllib.parse import urlparse
from urllib.request import urlopen


def check_postgres(postgres_dsn: str) -> tuple[bool, str | None]:
    try:
        import psycopg
    except ImportError:
        return False, "psycopg_not_installed"

    try:
        with psycopg.connect(postgres_dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception as exc:
        return False, str(exc).strip() or "postgres_connection_failed"

    return True, None


def check_redis(redis_url: str) -> tuple[bool, str | None]:
    parsed = urlparse(redis_url)
    host = parsed.hostname
    port = parsed.port or 6379

    if not host:
        return False, "invalid_redis_url"

    try:
        with socket.create_connection((host, port), timeout=2) as conn:
            conn.sendall(b"*1\r\n$4\r\nPING\r\n")
            response = conn.recv(64)
    except Exception as exc:
        return False, str(exc).strip() or "redis_connection_failed"

    if not response.startswith(b"+PONG"):
        return False, f"unexpected_redis_ping_response: {response!r}"

    return True, None


def check_minio(endpoint_url: str) -> tuple[bool, str | None]:
    endpoint = endpoint_url.rstrip("/")
    health_url = f"{endpoint}/minio/health/live"

    try:
        with urlopen(health_url, timeout=2) as response:  # noqa: S310
            if response.status < 200 or response.status >= 300:
                return False, f"http_status_{response.status}"
    except Exception as exc:
        return False, str(exc).strip() or "minio_connection_failed"

    return True, None
