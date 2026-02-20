from __future__ import annotations

from fastapi import APIRouter, Response

from caseflow.core.metrics import render_metrics_text

router = APIRouter()


@router.get("/metrics")
def metrics_endpoint() -> Response:
    return Response(
        content=render_metrics_text(),
        media_type="text/plain; version=0.0.4",
    )
