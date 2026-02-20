from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from caseflow.core.settings import get_settings


class CitationResponse(BaseModel):
    document_id: str
    chunk_id: str
    start_char: int
    end_char: int
    score: float


class JustificationResponse(BaseModel):
    summary: str
    reasons: list[str]
    citations: list[CitationResponse]


class PolicyResponse(BaseModel):
    policy_id: str
    decision: str
    reasons: list[str]
    derived: dict[str, float]


class UnderwriteResponseV1(BaseModel):
    schema_version: str = "v1"
    case_id: str
    decision: str
    risk_score: float
    policy: PolicyResponse
    justification: JustificationResponse
    request_id: str


class UnderwriteRequestArtifact(BaseModel):
    case_id: str
    request_id: str
    payload: dict[str, object]
    model_version: str | None = None
    evidence_query: str | None = None
    top_k: int = 5
    underwrite_engine: str = "graph"
    justifier_provider: str = "deterministic"


def _result_path(case_id: str, request_id: str) -> Path:
    settings = get_settings()
    safe_request_id = request_id.strip() or "no-request-id"
    return Path(settings.underwrite_results_dir) / case_id / f"{safe_request_id}.json"


def _request_path(case_id: str, request_id: str) -> Path:
    settings = get_settings()
    safe_request_id = request_id.strip() or "no-request-id"
    return (
        Path(settings.underwrite_results_dir)
        / case_id
        / f"{safe_request_id}_request.json"
    )


def save_underwrite_result(response: UnderwriteResponseV1) -> str:
    destination = _result_path(response.case_id, response.request_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(response.model_dump(), separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    return str(destination)


def load_underwrite_result(case_id: str, request_id: str) -> UnderwriteResponseV1:
    path = _result_path(case_id, request_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"No underwrite result found for case_id='{case_id}' and "
            f"request_id='{request_id}'."
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid underwrite result JSON at {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Underwrite result payload must be a JSON object")
    return UnderwriteResponseV1.model_validate(payload)


def save_underwrite_request(request: UnderwriteRequestArtifact) -> str:
    destination = _request_path(request.case_id, request.request_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(request.model_dump(), separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    return str(destination)


def load_underwrite_request(case_id: str, request_id: str) -> UnderwriteRequestArtifact:
    path = _request_path(case_id, request_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"No underwrite request found for case_id='{case_id}' "
            f"and request_id='{request_id}'."
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid underwrite request JSON at {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Underwrite request payload must be a JSON object")
    return UnderwriteRequestArtifact.model_validate(payload)
