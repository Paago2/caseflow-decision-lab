from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from caseflow.core.audit import get_audit_sink
from caseflow.core.metrics import increment_metric
from caseflow.domain.mortgage.evidence import EvidenceChunk
from caseflow.domain.mortgage.justification import generate_deterministic_justification
from caseflow.domain.mortgage.tools import (
    tool_evidence_search,
    tool_policy_check,
    tool_risk_score,
)
from caseflow.ml.vector_store import SearchResult

logger = logging.getLogger(__name__)


class UnderwriteGraphState(TypedDict):
    case_id: str
    payload: dict[str, object]
    model_version: str | None
    top_k: int
    evidence_query: str | None
    request_id: str
    policy_result: dict[str, object]
    risk_score: float
    model_id: str
    evidence_results: list[dict[str, object]]
    justification: dict[str, object]
    decision: str
    chunk_ids_used: list[str]


def build_default_evidence_query(payload: dict[str, object]) -> str:
    ordered_keys = [
        "credit_score",
        "monthly_income",
        "monthly_debt",
        "loan_amount",
        "property_value",
        "occupancy",
    ]
    parts: list[str] = []
    for key in ordered_keys:
        value = payload.get(key)
        if value is not None:
            parts.append(f"{key}={value}")

    if "monthly_income" in payload and "monthly_debt" in payload:
        try:
            income = float(payload["monthly_income"])
            debt = float(payload["monthly_debt"])
            dti = debt / income if income > 0 else 0.0
            parts.append(f"dti={dti:.4f}")
        except (TypeError, ValueError):
            pass

    return " | ".join(parts)


def node_policy_check(state: UnderwriteGraphState) -> UnderwriteGraphState:
    policy_result = tool_policy_check(state["payload"])
    return {
        **state,
        "policy_result": {
            "policy_id": policy_result.policy_id,
            "decision": policy_result.decision,
            "reasons": policy_result.reasons,
            "derived": policy_result.derived,
        },
    }


def node_risk_score(state: UnderwriteGraphState) -> UnderwriteGraphState:
    scored = tool_risk_score(state["payload"], state["model_version"])
    return {
        **state,
        "risk_score": scored.score,
        "model_id": scored.model_id,
    }


def node_build_query(state: UnderwriteGraphState) -> UnderwriteGraphState:
    query = state.get("evidence_query") or ""
    query = query.strip() if isinstance(query, str) else ""
    if not query:
        query = build_default_evidence_query(state["payload"])
    return {**state, "evidence_query": query}


def node_evidence_retrieve(state: UnderwriteGraphState) -> UnderwriteGraphState:
    query = state["evidence_query"] or ""
    matches = tool_evidence_search(state["case_id"], query, top_k=state["top_k"])
    serialized = [
        {
            "case_id": item.chunk.case_id,
            "document_id": item.chunk.document_id,
            "chunk_id": item.chunk.chunk_id,
            "text": item.chunk.text,
            "start_char": item.chunk.start_char,
            "end_char": item.chunk.end_char,
            "source": item.chunk.source,
            "page": item.chunk.page,
            "score": item.score,
        }
        for item in matches
    ]
    return {**state, "evidence_results": serialized}


def _deserialize_search_results(
    serialized: list[dict[str, object]],
) -> list[SearchResult]:
    out: list[SearchResult] = []
    for item in serialized:
        chunk = EvidenceChunk(
            case_id=str(item.get("case_id", "")),
            document_id=str(item.get("document_id", "")),
            chunk_id=str(item.get("chunk_id", "")),
            text=str(item.get("text", "")),
            start_char=int(item.get("start_char", 0)),
            end_char=int(item.get("end_char", 0)),
            source=str(item.get("source", "provenance")),
            page=(int(item["page"]) if isinstance(item.get("page"), int) else None),
        )
        out.append(SearchResult(chunk=chunk, score=float(item.get("score", 0.0))))
    return out


def node_justify(state: UnderwriteGraphState) -> UnderwriteGraphState:
    evidence_results = _deserialize_search_results(state["evidence_results"])
    policy_reasons = state["policy_result"].get("reasons", [])
    reasons = policy_reasons if isinstance(policy_reasons, list) else []

    justification = generate_deterministic_justification(
        decision=str(state["policy_result"].get("decision", "review")),
        policy_reasons=[str(item) for item in reasons],
        risk_score=float(state["risk_score"]),
        evidence_results=evidence_results,
    )

    citations = [
        {
            "document_id": citation.document_id,
            "chunk_id": citation.chunk_id,
            "start_char": citation.start_char,
            "end_char": citation.end_char,
            "score": citation.score,
        }
        for citation in justification.citations
    ]
    chunk_ids_used = [str(item["chunk_id"]) for item in citations]

    return {
        **state,
        "justification": {
            "summary": justification.summary,
            "reasons": justification.reasons,
            "citations": citations,
        },
        "chunk_ids_used": chunk_ids_used,
    }


def node_decide(state: UnderwriteGraphState) -> UnderwriteGraphState:
    decision = str(state["policy_result"].get("decision", "review"))
    return {**state, "decision": decision}


def node_audit_metrics(state: UnderwriteGraphState) -> UnderwriteGraphState:
    citation_count = len(state["chunk_ids_used"])
    increment_metric("underwrite_citations_total", float(citation_count))
    if citation_count > 0:
        increment_metric("underwrite_with_citations_total")

    audit_event = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "request_id": state["request_id"],
        "case_id": state["case_id"],
        "event": "underwrite_justification",
        "decision": state["decision"],
        "risk_score": state["risk_score"],
        "model_id": state["model_id"],
        "chunk_ids": state["chunk_ids_used"],
    }
    try:
        get_audit_sink().emit_decision_event(audit_event)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "underwrite_graph_audit_emit_failed",
            extra={
                "event": "underwrite_graph_audit_emit_failed",
                "request_id": state["request_id"],
                "case_id": state["case_id"],
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            },
        )
    return state


def build_underwrite_graph():
    graph = StateGraph(UnderwriteGraphState)
    graph.add_node("policy", node_policy_check)
    graph.add_node("risk", node_risk_score)
    graph.add_node("build_query", node_build_query)
    graph.add_node("evidence", node_evidence_retrieve)
    graph.add_node("justify", node_justify)
    graph.add_node("decide", node_decide)
    graph.add_node("audit_metrics", node_audit_metrics)

    graph.add_edge(START, "policy")
    graph.add_edge("policy", "risk")
    graph.add_edge("risk", "build_query")
    graph.add_edge("build_query", "evidence")
    graph.add_edge("evidence", "justify")
    graph.add_edge("justify", "decide")
    graph.add_edge("decide", "audit_metrics")
    graph.add_edge("audit_metrics", END)
    return graph.compile()


_underwrite_graph = build_underwrite_graph()


def run_underwrite_graph(state: UnderwriteGraphState) -> UnderwriteGraphState:
    return _underwrite_graph.invoke(state)
