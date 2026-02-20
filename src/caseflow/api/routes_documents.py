from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from caseflow.domain.mortgage.documents import (
    extract_features_from_documents,
    missing_required,
)
from caseflow.domain.mortgage.policy import evaluate_mortgage_policy_v1

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_documents_payload(payload: Any) -> tuple[str, list[dict[str, Any]]]:
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

    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise HTTPException(
            status_code=422,
            detail="'documents' must be a non-empty list",
        )

    for item in documents:
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=422,
                detail="Each document must be a JSON object",
            )

    return case_id.strip(), documents


@router.post("/documents/intake")
async def documents_intake_endpoint(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    case_id, documents = _parse_documents_payload(payload)

    try:
        extracted_features, source_summary = extract_features_from_documents(documents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    missing = missing_required(extracted_features)
    request_id = getattr(request.state, "request_id", "") or ""

    logger.info(
        "documents_intake_completed",
        extra={
            "event": "documents_intake_completed",
            "case_id": case_id,
            "doc_count": len(documents),
            "source_summary": source_summary,
            "missing_count": len(missing),
            "request_id": request_id,
        },
    )

    return {
        "case_id": case_id,
        "extracted_features": extracted_features,
        "missing": missing,
        "source_summary": source_summary,
        "request_id": request_id,
    }


@router.post("/documents/decision")
async def documents_decision_endpoint(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    case_id, documents = _parse_documents_payload(payload)

    try:
        extracted_features, source_summary = extract_features_from_documents(documents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    missing = missing_required(extracted_features)
    if missing:
        raise HTTPException(
            status_code=422,
            detail="Missing required downstream fields: " + ", ".join(missing),
        )

    policy_features: dict[str, object] = {
        "credit_score": extracted_features["credit_score"],
        "monthly_income": extracted_features["gross_monthly_income"],
        "monthly_debt": extracted_features["total_monthly_debt"],
        "loan_amount": extracted_features["loan_amount"],
        "property_value": extracted_features["property_value"],
        "occupancy": extracted_features["occupancy"],
    }

    try:
        result = evaluate_mortgage_policy_v1({"features": policy_features})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    request_id = getattr(request.state, "request_id", "") or ""
    logger.info(
        "documents_decision_completed",
        extra={
            "event": "documents_decision_completed",
            "case_id": case_id,
            "policy_id": result.policy_id,
            "decision": result.decision,
            "source_summary": source_summary,
            "request_id": request_id,
        },
    )

    return {
        "case_id": case_id,
        "policy_id": result.policy_id,
        "decision": result.decision,
        "reasons": result.reasons,
        "derived": result.derived,
        "extracted_features": extracted_features,
        "missing": missing,
        "request_id": request_id,
    }
