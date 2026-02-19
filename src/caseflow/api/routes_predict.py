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

    request_id = getattr(request.state, "request_id", "") or ""

    return {
        "model_id": model.model_id,
        "score": score,
        "request_id": request_id,
    }
