from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from caseflow.ml.registry import get_active_model

router = APIRouter()


@router.post("/predict")
async def predict_endpoint(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400, detail="Request body must be a JSON object"
        )

    features = payload.get("features")

    if not isinstance(features, list):
        raise HTTPException(
            status_code=400, detail="'features' must be a list of numbers"
        )

    try:
        numeric_features = [float(value) for value in features]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="'features' must contain only numeric values",
        ) from exc

    model = get_active_model()
    try:
        score = model.predict(numeric_features)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    request_id = getattr(request.state, "request_id", "") or ""

    return {
        "model_id": model.model_id,
        "score": score,
        "request_id": request_id,
    }
