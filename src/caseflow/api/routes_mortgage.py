from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from caseflow.core.audit import get_audit_sink
from caseflow.domain.mortgage.policy import evaluate_mortgage_policy_v1

router = APIRouter()
logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {
    "credit_score",
    "monthly_income",
    "monthly_debt",
    "loan_amount",
    "property_value",
    "occupancy",
}
_NUMERIC_KEYS = {
    "credit_score",
    "monthly_income",
    "monthly_debt",
    "loan_amount",
    "property_value",
}


@router.post("/mortgage/decision")
async def mortgage_decision_endpoint(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400, detail="Request body must be a JSON object"
        )

    features = payload.get("features")
    if not isinstance(features, dict):
        raise HTTPException(status_code=422, detail="'features' must be an object")

    missing_keys = sorted(_REQUIRED_KEYS - set(features.keys()))
    if missing_keys:
        raise HTTPException(
            status_code=422,
            detail="Missing required feature keys: " + ", ".join(missing_keys),
        )

    occupancy = features.get("occupancy")
    if not isinstance(occupancy, str) or occupancy not in {
        "primary",
        "secondary",
        "investment",
    }:
        raise HTTPException(
            status_code=422,
            detail="'occupancy' must be one of: primary, secondary, investment",
        )

    for key in _NUMERIC_KEYS:
        try:
            features[key] = float(features[key])
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"'{key}' must be numeric",
            ) from exc

    try:
        result = evaluate_mortgage_policy_v1(features)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    request_id = getattr(request.state, "request_id", "") or ""
    logger.info(
        "mortgage_decision_made",
        extra={
            "event": "mortgage_decision_made",
            "decision": result.decision,
            "policy_id": result.policy_id,
            "request_id": request_id,
        },
    )

    audit_event = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "request_id": request_id,
        "policy_id": result.policy_id,
        "decision": result.decision,
        "reasons": result.reasons,
        "derived": result.derived,
    }
    try:
        get_audit_sink().emit_decision_event(audit_event)
    except Exception as exc:  # pragma: no cover
        logger.error(
            "mortgage_audit_emit_failed",
            extra={
                "event": "mortgage_audit_emit_failed",
                "request_id": request_id,
                "policy_id": result.policy_id,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            },
        )

    return {
        "policy_id": result.policy_id,
        "decision": result.decision,
        "reasons": result.reasons,
        "derived": result.derived,
        "request_id": request_id,
    }
