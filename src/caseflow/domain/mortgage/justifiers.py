from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from caseflow.domain.mortgage.justification import Citation, Justification
from caseflow.ml.vector_store import SearchResult


class Justifier(Protocol):
    def generate(
        self,
        *,
        case_id: str,
        payload: dict[str, object],
        policy_result: dict[str, object],
        risk_score: float,
        evidence_results: list[SearchResult],
        max_citations: int,
        request_id: str,
    ) -> Justification: ...


def _build_justification(
    *,
    decision: str,
    policy_reasons: list[str],
    risk_score: float,
    evidence_results: list[SearchResult],
    max_citations: int,
) -> Justification:
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


@dataclass
class DeterministicJustifier:
    def generate(
        self,
        *,
        case_id: str,
        payload: dict[str, object],
        policy_result: dict[str, object],
        risk_score: float,
        evidence_results: list[SearchResult],
        max_citations: int,
        request_id: str,
    ) -> Justification:
        del case_id, payload, request_id
        reasons = policy_result.get("reasons", [])
        policy_reasons = (
            [str(item) for item in reasons] if isinstance(reasons, list) else []
        )
        return _build_justification(
            decision=str(policy_result.get("decision", "review")),
            policy_reasons=policy_reasons,
            risk_score=risk_score,
            evidence_results=evidence_results,
            max_citations=max_citations,
        )


@dataclass
class StubLLMJustifier:
    transcript: dict[str, object] = field(default_factory=dict)

    def generate(
        self,
        *,
        case_id: str,
        payload: dict[str, object],
        policy_result: dict[str, object],
        risk_score: float,
        evidence_results: list[SearchResult],
        max_citations: int,
        request_id: str,
    ) -> Justification:
        justification = _build_justification(
            decision=str(policy_result.get("decision", "review")),
            policy_reasons=[str(item) for item in policy_result.get("reasons", [])],
            risk_score=risk_score,
            evidence_results=evidence_results,
            max_citations=max_citations,
        )

        payload_keys = sorted(payload.keys())
        selected_chunk_ids = [citation.chunk_id for citation in justification.citations]
        self.transcript = {
            "provider": "stub_llm",
            "request_id": request_id,
            "case_id": case_id,
            "tools_called": ["policy_check", "risk_score", "evidence_search"],
            "inputs": {
                "payload_keys": payload_keys,
                "evidence_count": len(evidence_results),
                "max_citations": max_citations,
            },
            "outputs": {
                "policy_decision": str(policy_result.get("decision", "review")),
                "risk_score": float(risk_score),
                "selected_chunk_ids": selected_chunk_ids,
            },
        }
        return justification


def get_justifier(provider: str) -> Justifier:
    if provider == "stub_llm":
        return StubLLMJustifier()
    return DeterministicJustifier()
