from fastapi import FastAPI

from caseflow.api.routes_ready import router as ready_router

app = FastAPI(title="caseflow-decision-lab API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ready_router)
