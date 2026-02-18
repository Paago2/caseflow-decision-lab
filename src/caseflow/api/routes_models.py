from __future__ import annotations

from fastapi import APIRouter, HTTPException, Security

from caseflow.core.auth import require_api_key
from caseflow.ml.registry import get_active_model, list_model_ids, set_active_model

router = APIRouter(dependencies=[Security(require_api_key)])


@router.get("/models")
def get_models() -> dict[str, object]:
    active_model = get_active_model()
    return {
        "active_model_id": active_model.model_id,
        "available_model_ids": list_model_ids(),
    }


@router.post("/models/activate/{model_id}")
def activate_model(model_id: str) -> dict[str, str]:
    try:
        active_model = set_active_model(model_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"active_model_id": active_model.model_id}
