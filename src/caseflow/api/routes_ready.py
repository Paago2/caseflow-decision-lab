from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from caseflow.core.deps_health import check_minio, check_postgres, check_redis
from caseflow.core.settings import get_settings
from caseflow.ml.registry import get_active_model

router = APIRouter()
VALID_APP_ENVS = {"local", "dev", "stg", "prod"}


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    settings = get_settings()
    api_key_required = settings.app_env != "local"

    postgres_ok, postgres_detail = check_postgres(settings.postgres_dsn)
    redis_ok, redis_detail = check_redis(settings.redis_url)
    minio_ok, minio_detail = check_minio(settings.s3_endpoint_url)

    model_loaded = True
    model_reason: str | None = None

    try:
        get_active_model()
    except RuntimeError as exc:
        model_loaded = False
        startup_model_status = getattr(request.app.state, "startup_model_status", {})
        reason = startup_model_status.get("reason")
        detail = startup_model_status.get("detail")

        if isinstance(reason, str) and reason.strip():
            model_reason = reason.strip()
            if isinstance(detail, str) and detail.strip():
                model_reason = f"{model_reason}: {detail.strip()}"
        else:
            model_reason = f"model_not_loaded: {str(exc).strip()}"

    checks = {
        "env_loaded": True,
        "api_key_set": bool(settings.api_key.strip()) or not api_key_required,
        "app_env_valid": settings.app_env in VALID_APP_ENVS,
        "postgres_ok": postgres_ok,
        "redis_ok": redis_ok,
        "minio_ok": minio_ok,
        "model_loaded": model_loaded,
    }

    all_checks_passed = all(checks.values())
    payload = {
        "status": "ready" if all_checks_passed else "not_ready",
        "checks": checks,
    }

    if not all_checks_passed:
        if not checks["postgres_ok"]:
            payload["reason"] = f"postgres_not_ready: {postgres_detail or 'unknown'}"
        elif not checks["redis_ok"]:
            payload["reason"] = f"redis_not_ready: {redis_detail or 'unknown'}"
        elif not checks["minio_ok"]:
            payload["reason"] = f"minio_not_ready: {minio_detail or 'unknown'}"
        elif not checks["model_loaded"] and model_reason:
            payload["reason"] = model_reason
        elif not checks["api_key_set"]:
            payload["reason"] = "api_key_not_set"
        elif not checks["app_env_valid"]:
            payload["reason"] = "app_env_invalid"
        else:
            payload["reason"] = "readiness_checks_failed"

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if all_checks_passed
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content=payload,
    )
