from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from caseflow.agents.underwriter_agent import (
    UnderwriterCase,
    run_underwriter_agent,
    underwrite_case_with_justification,
)
from caseflow.agents.underwriter_graph import load_underwrite_trace

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


def _validate_mortgage_payload(payload: dict[str, object]) -> dict[str, object]:
    missing_keys = sorted(_REQUIRED_KEYS - set(payload.keys()))
    if missing_keys:
        raise HTTPException(
            status_code=422,
            detail="Missing required feature keys: " + ", ".join(missing_keys),
        )

    occupancy = payload.get("occupancy")
    if not isinstance(occupancy, str) or occupancy not in {
        "primary",
        "secondary",
        "investment",
    }:
        raise HTTPException(
            status_code=422,
            detail="'occupancy' must be one of: primary, secondary, investment",
        )

    normalized = dict(payload)
    for key in _NUMERIC_KEYS:
        try:
            normalized[key] = float(normalized[key])
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"'{key}' must be numeric",
            ) from exc

    return normalized


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

    normalized_features = _validate_mortgage_payload(features)

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


@router.post("/mortgage/{case_id}/underwrite")
async def mortgage_underwrite_endpoint(
    case_id: str,
    request: Request,
) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON object",
        )

    normalized_case_id = case_id.strip()
    if not normalized_case_id:
        raise HTTPException(
            status_code=422,
            detail="'case_id' must be a non-empty string",
        )

    payload_value = body.get("payload")
    if not isinstance(payload_value, dict):
        raise HTTPException(status_code=422, detail="'payload' must be an object")

    model_version_raw = body.get("model_version")
    if model_version_raw is None:
        model_version: str | None = None
    elif isinstance(model_version_raw, str) and model_version_raw.strip():
        model_version = model_version_raw.strip()
    else:
        raise HTTPException(
            status_code=422,
            detail="'model_version' must be a non-empty string when provided",
        )

    evidence_query_raw = body.get("evidence_query")
    if evidence_query_raw is None:
        evidence_query: str | None = None
    elif isinstance(evidence_query_raw, str):
        evidence_query = evidence_query_raw
    else:
        raise HTTPException(
            status_code=422,
            detail="'evidence_query' must be a string when provided",
        )

    top_k_raw = body.get("top_k", 5)
    try:
        top_k = int(top_k_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="'top_k' must be an integer"
        ) from exc

    if top_k < 1:
        raise HTTPException(status_code=422, detail="'top_k' must be >= 1")

    normalized_payload = _validate_mortgage_payload(payload_value)
    request_id = getattr(request.state, "request_id", "") or ""

    try:
        result = underwrite_case_with_justification(
            normalized_case_id,
            normalized_payload,
            model_version=model_version,
            evidence_query=evidence_query,
            top_k=top_k,
            request_id=request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    logger.info(
        "mortgage_underwrite_completed",
        extra={
            "event": "mortgage_underwrite_completed",
            "case_id": normalized_case_id,
            "decision": result.decision,
            "score": result.risk_score,
            "num_citations": len(result.justification.citations),
            "model_version": model_version or result.model_id,
            "top_k": top_k,
            "request_id": request_id,
        },
    )

    return {
        "case_id": normalized_case_id,
        "decision": result.decision,
        "risk_score": result.risk_score,
        "policy": result.policy,
        "justification": {
            "summary": result.justification.summary,
            "reasons": result.justification.reasons,
            "citations": [
                {
                    "document_id": citation.document_id,
                    "chunk_id": citation.chunk_id,
                    "start_char": citation.start_char,
                    "end_char": citation.end_char,
                    "score": citation.score,
                }
                for citation in result.justification.citations
            ],
        },
        "request_id": request_id,
    }


@router.get("/mortgage/{case_id}/underwrite/trace")
async def mortgage_underwrite_trace_endpoint(
    case_id: str,
    request: Request,
    request_id: str = Query(..., min_length=1),
) -> dict[str, object]:
    normalized_case_id = case_id.strip()
    if not normalized_case_id:
        raise HTTPException(
            status_code=422,
            detail="'case_id' must be a non-empty string",
        )

    normalized_request_id = request_id.strip()
    if not normalized_request_id:
        raise HTTPException(
            status_code=422,
            detail="'request_id' must be a non-empty string",
        )

    try:
        trace = load_underwrite_trace(normalized_case_id, normalized_request_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    response_request_id = getattr(request.state, "request_id", "") or ""
    return {
        "case_id": normalized_case_id,
        "request_id": response_request_id,
        "trace": trace,
    }
