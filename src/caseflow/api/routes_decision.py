from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from caseflow.core.audit import get_audit_sink
from caseflow.ml.registry import get_active_model

router = APIRouter()
logger = logging.getLogger(__name__)

APPROVE_THRESHOLD = 200.0
DECLINE_THRESHOLD = 120.0


@router.post("/decision")
async def decision_endpoint(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400, detail="Request body must be a JSON object"
        )

    features = payload.get("features")
    model = get_active_model()

    if isinstance(features, list):
        try:
            numeric_features = [float(value) for value in features]
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail="'features' must contain only numeric values",
            ) from exc
    elif isinstance(features, dict):
        try:
            numeric_features = model.vector_from_named_features(features)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        raise HTTPException(
            status_code=400,
            detail="'features' must be a list of numbers or an object",
        )

    try:
        score = model.predict(numeric_features)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if score >= APPROVE_THRESHOLD:
        decision = "approve"
        reasons = ["score_above_approve_threshold"]
    elif score <= DECLINE_THRESHOLD:
        decision = "decline"
        reasons = ["score_below_decline_threshold"]
    else:
        decision = "review"
        reasons = ["score_in_review_band"]

    request_id = getattr(request.state, "request_id", "") or ""
    logger.info(
        "decision_made",
        extra={
            "event": "decision_made",
            "decision": decision,
            "score": score,
            "model_id": model.model_id,
            "request_id": request_id,
        },
    )

    audit_event = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "request_id": request_id,
        "model_id": model.model_id,
        "score": score,
        "decision": decision,
        "reasons": reasons,
    }
    try:
        get_audit_sink().emit_decision_event(audit_event)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "decision_audit_emit_failed",
            extra={
                "event": "decision_audit_emit_failed",
                "request_id": request_id,
                "model_id": model.model_id,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            },
        )

    return {
        "model_id": model.model_id,
        "score": score,
        "decision": decision,
        "reasons": reasons,
        "request_id": request_id,
    }
