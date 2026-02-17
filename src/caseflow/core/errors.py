from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from caseflow.core.request_id import REQUEST_ID_HEADER

logger = logging.getLogger(__name__)


def _request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", "") or ""


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        request_id = _request_id_from(request)
        logger.info(
            "http_exception",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
            },
        )

        response = JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": str(exc.detail),
                    "status": exc.status_code,
                    "request_id": request_id,
                }
            },
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = _request_id_from(request)
        logger.error(
            "unhandled_exception",
            exc_info=True,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )

        response = JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Internal Server Error",
                    "status": 500,
                    "request_id": request_id,
                }
            },
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
