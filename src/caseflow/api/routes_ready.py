from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from caseflow.core.settings import get_settings

router = APIRouter()
VALID_APP_ENVS = {"local", "dev", "stg", "prod"}


@router.get("/ready")
def ready() -> JSONResponse:
    settings = get_settings()

    checks = {
        "env_loaded": True,
        "api_key_set": bool(settings.api_key.strip()),
        "app_env_valid": settings.app_env in VALID_APP_ENVS,
    }

    all_checks_passed = all(checks.values())
    payload = {
        "status": "ready" if all_checks_passed else "not_ready",
        "checks": checks,
    }

    return JSONResponse(
        status_code=status.HTTP_200_OK
        if all_checks_passed
        else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )
