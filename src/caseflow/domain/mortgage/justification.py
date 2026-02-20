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
    max_citations = get_settings().evidence_max_citations
    ordered = sorted(
        evidence_results,
        key=lambda item: (-item.score, item.chunk.chunk_id),
    )
    top = ordered[:max_citations] if max_citations > 0 else []

    citations = [
        Citation(
            document_id=item.chunk.document_id,
            chunk_id=item.chunk.chunk_id,
            start_char=item.chunk.start_char,
            end_char=item.chunk.end_char,
            score=float(item.score),
        )
        for item in top
    ]

    if risk_score < 120:
        risk_band = "low"
    elif risk_score < 200:
        risk_band = "moderate"
    else:
        risk_band = "high"

    summary = (
        f"Policy decision is {decision}. Deterministic risk score is "
        f"{risk_score:.4f} ({risk_band} band)."
    )

    if not citations:
        return Justification(
            summary="No supporting evidence indexed for this case.",
            reasons=[
                f"Policy decision is {decision} based on rule evaluation.",
                "No supporting evidence indexed for this case.",
            ],
            citations=[],
        )

    reasons: list[str] = []
    reasons.append(f"Policy signals: {', '.join(policy_reasons)} (see C1).")
    reasons.append(f"Risk score is {risk_score:.4f} in the {risk_band} band (see C1).")
    for index, citation in enumerate(citations[1:], start=2):
        reasons.append(
            "Additional supporting evidence from document "
            f"{citation.document_id} (see C{index})."
        )

    return Justification(summary=summary, reasons=reasons[:5], citations=citations)
