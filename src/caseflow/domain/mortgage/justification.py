from __future__ import annotations

from dataclasses import dataclass

from caseflow.core.settings import get_settings
from caseflow.ml.vector_store import SearchResult


@dataclass(frozen=True)
class Citation:
    document_id: str
    chunk_id: str
    start_char: int
    end_char: int
    score: float


@dataclass(frozen=True)
class Justification:
    summary: str
    reasons: list[str]
    citations: list[Citation]


def generate_deterministic_justification(
    *,
    decision: str,
    policy_reasons: list[str],
    risk_score: float,
    evidence_results: list[SearchResult],
) -> Justification:
    from caseflow.domain.mortgage.justifiers import DeterministicJustifier

    return DeterministicJustifier().generate(
        case_id="",
        payload={},
        policy_result={"decision": decision, "reasons": policy_reasons},
        risk_score=risk_score,
        evidence_results=evidence_results,
        max_citations=get_settings().evidence_max_citations,
        request_id="",
    )
