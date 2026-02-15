from fastapi import APIRouter, Depends, FastAPI

from caseflow.api.routes_ready import router as ready_router
from caseflow.core.auth import require_api_key

app = FastAPI(title="caseflow-decision-lab API")
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
app.include_router(protected_router)
