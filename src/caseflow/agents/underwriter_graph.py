from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from caseflow.core.audit import get_audit_sink
from caseflow.core.metrics import increment_metric
from caseflow.core.settings import get_settings
from caseflow.domain.mortgage.evidence import EvidenceChunk
from caseflow.domain.mortgage.justifiers import StubLLMJustifier, get_justifier
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
    trace_events: list[dict[str, object]]
    justifier_transcript: dict[str, object]


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


def _append_trace_event(
    state: UnderwriteGraphState,
    node_name: str,
    *,
    started_at: float,
    outputs: dict[str, object],
) -> list[dict[str, object]]:
    duration_ms = (perf_counter() - started_at) * 1000
    events = list(state.get("trace_events", []))
    events.append(
        {
            "node_name": node_name,
            "duration_ms": round(duration_ms, 3),
            "outputs": outputs,
        }
    )
    return events


def node_policy_check(state: UnderwriteGraphState) -> UnderwriteGraphState:
    started = perf_counter()
    policy_result = tool_policy_check(state["payload"])
    policy_payload = {
        "policy_id": policy_result.policy_id,
        "decision": policy_result.decision,
        "reasons": policy_result.reasons,
        "derived": policy_result.derived,
    }
    return {
        **state,
        "policy_result": policy_payload,
        "trace_events": _append_trace_event(
            state,
            "policy",
            started_at=started,
            outputs={
                "policy_id": policy_result.policy_id,
                "decision": policy_result.decision,
            },
        ),
    }


def node_risk_score(state: UnderwriteGraphState) -> UnderwriteGraphState:
    started = perf_counter()
    scored = tool_risk_score(state["payload"], state["model_version"])
    return {
        **state,
        "risk_score": scored.score,
        "model_id": scored.model_id,
        "trace_events": _append_trace_event(
            state,
            "risk",
            started_at=started,
            outputs={
                "risk_score": float(scored.score),
                "model_id": scored.model_id,
            },
        ),
    }


def node_build_query(state: UnderwriteGraphState) -> UnderwriteGraphState:
    started = perf_counter()
    query = state.get("evidence_query") or ""
    query = query.strip() if isinstance(query, str) else ""
    if not query:
        query = build_default_evidence_query(state["payload"])
    return {
        **state,
        "evidence_query": query,
        "trace_events": _append_trace_event(
            state,
            "build_query",
            started_at=started,
            outputs={"query_length": len(query)},
        ),
    }


def node_evidence_retrieve(state: UnderwriteGraphState) -> UnderwriteGraphState:
    started = perf_counter()
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
    return {
        **state,
        "evidence_results": serialized,
        "trace_events": _append_trace_event(
            state,
            "evidence",
            started_at=started,
            outputs={
                "result_count": len(serialized),
                "chunk_ids": [str(item["chunk_id"]) for item in serialized],
            },
        ),
    }


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
    started = perf_counter()
    evidence_results = _deserialize_search_results(state["evidence_results"])
    settings = get_settings()
    justifier = get_justifier(settings.justifier_provider)
    justification = justifier.generate(
        case_id=state["case_id"],
        payload=state["payload"],
        policy_result=state["policy_result"],
        risk_score=float(state["risk_score"]),
        evidence_results=evidence_results,
        max_citations=settings.evidence_max_citations,
        request_id=state["request_id"],
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
    transcript: dict[str, object] = {}
    if isinstance(justifier, StubLLMJustifier):
        transcript = dict(justifier.transcript)

    return {
        **state,
        "justification": {
            "summary": justification.summary,
            "reasons": justification.reasons,
            "citations": citations,
        },
        "chunk_ids_used": chunk_ids_used,
        "justifier_transcript": transcript,
        "trace_events": _append_trace_event(
            state,
            "justify",
            started_at=started,
            outputs={
                "provider": settings.justifier_provider,
                "num_citations": len(citations),
                "chunk_ids": chunk_ids_used,
            },
        ),
    }


def node_decide(state: UnderwriteGraphState) -> UnderwriteGraphState:
    started = perf_counter()
    decision = str(state["policy_result"].get("decision", "review"))
    return {
        **state,
        "decision": decision,
        "trace_events": _append_trace_event(
            state,
            "decide",
            started_at=started,
            outputs={"decision": decision},
        ),
    }


def node_audit_metrics(state: UnderwriteGraphState) -> UnderwriteGraphState:
    started = perf_counter()
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
    return {
        **state,
        "trace_events": _append_trace_event(
            state,
            "audit_metrics",
            started_at=started,
            outputs={
                "citation_count": citation_count,
                "decision": state["decision"],
            },
        ),
    }


def _trace_path(case_id: str, request_id: str) -> Path:
    settings = get_settings()
    safe_request_id = request_id.strip() or "no-request-id"
    return Path(settings.trace_dir) / case_id / f"{safe_request_id}.json"


def _write_trace(state: UnderwriteGraphState) -> None:
    if not get_settings().trace_enabled:
        return

    trace_payload = {
        "case_id": state["case_id"],
        "request_id": state["request_id"],
        "decision": state["decision"],
        "risk_score": state["risk_score"],
        "model_id": state["model_id"],
        "chunk_ids_used": state["chunk_ids_used"],
        "trace": state.get("trace_events", []),
        "justifier_transcript": state.get("justifier_transcript", {}),
    }
    destination = _trace_path(state["case_id"], state["request_id"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(trace_payload, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )


def load_underwrite_trace(case_id: str, request_id: str) -> dict[str, object]:
    path = _trace_path(case_id, request_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"No trace found for case_id='{case_id}' and request_id='{request_id}'."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid trace JSON at {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Trace payload must be a JSON object")
    return payload


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
    final_state = _underwrite_graph.invoke(state)
    _write_trace(final_state)
    return final_state
