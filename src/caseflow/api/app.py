import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Security

from caseflow.api.routes_decision import router as decision_router
from caseflow.api.routes_models import router as models_router
from caseflow.api.routes_predict import router as predict_router
from caseflow.api.routes_ready import router as ready_router
from caseflow.api.routes_version import router as version_router
from caseflow.core.auth import require_api_key
from caseflow.core.errors import install_error_handlers
from caseflow.core.logging import configure_logging
from caseflow.core.request_id import install_request_id_middleware
from caseflow.core.settings import get_settings
from caseflow.ml.registry import clear_active_model, set_active_model

configure_logging()

request_id_logger = logging.getLogger("caseflow.core.request_id")
request_id_logger.setLevel(logging.INFO)
request_id_logger.propagate = True

logger = logging.getLogger(__name__)


def _safe_error_message(message: str, max_length: int = 180) -> str:
    sanitized = " ".join(message.split())
    if not sanitized:
        return "unknown_error"
    return sanitized[:max_length]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    clear_active_model()

    try:
        set_active_model(settings.active_model_id)
    except Exception as exc:  # pragma: no cover - broad on purpose for startup safety
        error_message = _safe_error_message(str(exc))
        app.state.startup_model_status = {
            "loaded": False,
            "reason": "model_not_loaded",
            "detail": error_message,
        }
        logger.error(
            "startup model load failed",
            extra={
                "event": "startup_model_load_failed",
                "active_model_id": settings.active_model_id,
                "model_registry_dir": settings.model_registry_dir,
                "error_type": exc.__class__.__name__,
                "error_message": error_message,
            },
        )
    else:
        app.state.startup_model_status = {
            "loaded": True,
            "reason": None,
            "detail": None,
        }
        logger.info(
            "startup model loaded",
            extra={
                "event": "startup_model_loaded",
                "active_model_id": settings.active_model_id,
            },
        )

    try:
        yield
    finally:
        clear_active_model()


app = FastAPI(title="caseflow-decision-lab API", lifespan=lifespan)
install_request_id_middleware(app)
install_error_handlers(app)

protected_router = APIRouter(
    prefix="/protected",
    dependencies=[Security(require_api_key)],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@protected_router.get("/ping")
def protected_ping() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ready_router)
app.include_router(version_router)
app.include_router(predict_router)
app.include_router(decision_router)
app.include_router(models_router)
app.include_router(protected_router)
