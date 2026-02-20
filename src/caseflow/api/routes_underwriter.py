from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from caseflow.agents.underwriter_agent import UnderwriterCase, run_underwriter_agent

router = APIRouter()

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


@router.post("/underwriter/run")
async def underwriter_run_endpoint(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON object",
        )

    case_id = payload.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise HTTPException(
            status_code=422,
            detail="'case_id' must be a non-empty string",
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

    normalized_features = dict(features)
    for key in _NUMERIC_KEYS:
        try:
            normalized_features[key] = float(normalized_features[key])
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"'{key}' must be numeric",
            ) from exc

    request_id = getattr(request.state, "request_id", "") or ""
    result = run_underwriter_agent(
        UnderwriterCase(case_id=case_id.strip(), features=normalized_features),
        request_id=request_id,
    )

    return {
        "case_id": result.case_id,
        "policy_id": result.policy_id,
        "decision": result.decision,
        "reasons": result.reasons,
        "derived": result.derived,
        "next_actions": result.next_actions,
        "request_id": result.request_id,
    }
