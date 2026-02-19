from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from caseflow.core.request_id import REQUEST_ID_HEADER
from caseflow.core.settings import get_settings

logger = logging.getLogger(__name__)

LIMITED_PATHS = {"/predict", "/decision"}


@dataclass
class _TokenBucket:
    tokens: float
    last_refill: float


class TokenBucketRateLimiter:
    def __init__(self, rps: float, burst: int) -> None:
        self._rps = rps
        self._burst = float(burst)
        self._buckets: dict[str, _TokenBucket] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _TokenBucket(tokens=self._burst, last_refill=now)
                self._buckets[key] = bucket

            elapsed = now - bucket.last_refill
            bucket.last_refill = now
            bucket.tokens = min(self._burst, bucket.tokens + elapsed * self._rps)

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True

            return False


_limiter: TokenBucketRateLimiter | None = None


def _get_limiter() -> TokenBucketRateLimiter:
    global _limiter
    settings = get_settings()

    if _limiter is None:
        _limiter = TokenBucketRateLimiter(
            rps=settings.rate_limit_rps,
            burst=settings.rate_limit_burst,
        )
    return _limiter


def clear_rate_limiter_cache() -> None:
    global _limiter
    _limiter = None


def install_rate_limit_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled or request.url.path not in LIMITED_PATHS:
            return await call_next(request)

        client_host = (
            request.client.host if request.client and request.client.host else "unknown"
        )
        key = client_host if settings.rate_limit_scope == "ip" else "global"

        if _get_limiter().allow(key):
            return await call_next(request)

        request_id = (
            getattr(request.state, "request_id", "")
            or request.headers.get(REQUEST_ID_HEADER)
            or str(uuid4())
        )
        logger.info(
            "rate_limit_exceeded",
            extra={
                "event": "rate_limit_exceeded",
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": 429,
            },
        )

        response = JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "http_error",
                    "message": "Rate limit exceeded",
                    "status": 429,
                    "request_id": request_id,
                }
            },
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
