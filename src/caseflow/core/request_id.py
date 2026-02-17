from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response

logger = logging.getLogger(__name__)
REQUEST_ID_HEADER = "X-Request-Id"


def install_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
