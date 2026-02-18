import logging

from fastapi import APIRouter, FastAPI, Security

from caseflow.api.routes_predict import router as predict_router
from caseflow.api.routes_ready import router as ready_router
from caseflow.api.routes_version import router as version_router
from caseflow.core.auth import require_api_key
from caseflow.core.errors import install_error_handlers
from caseflow.core.logging import configure_logging
from caseflow.core.request_id import install_request_id_middleware

app = FastAPI(title="caseflow-decision-lab API")
configure_logging()

request_id_logger = logging.getLogger("caseflow.core.request_id")
request_id_logger.setLevel(logging.INFO)
request_id_logger.propagate = True

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
app.include_router(protected_router)
