from fastapi import FastAPI

app = FastAPI(title="caseflow-decision-lab API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
