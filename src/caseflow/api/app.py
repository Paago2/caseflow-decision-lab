from fastapi import APIRouter, Depends, FastAPI

from caseflow.api.routes_ready import router as ready_router
from caseflow.api.routes_version import router as version_router
from caseflow.core.auth import require_api_key
from caseflow.core.request_id import install_request_id_middleware

app = FastAPI(title="caseflow-decision-lab API")
install_request_id_middleware(app)

protected_router = APIRouter(
    prefix="/protected",
    dependencies=[Depends(require_api_key)],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@protected_router.get("/ping")
def protected_ping() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ready_router)
app.include_router(version_router)
app.include_router(protected_router)
