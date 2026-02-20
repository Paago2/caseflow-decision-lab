from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import START, StateGraph

from caseflow.agents.underwriter_graph import run_underwrite_graph
from caseflow.core.settings import get_settings
from caseflow.domain.mortgage.justification import (
    Justification,
    generate_deterministic_justification,
)
from caseflow.domain.mortgage.policy import evaluate_mortgage_policy_v1
from caseflow.domain.mortgage.tools import (
    RiskScoreResult,
    tool_evidence_search,
    tool_policy_check,
    tool_risk_score,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UnderwriterCase:
    case_id: str
    features: dict[str, object]


@dataclass(frozen=True)
class UnderwriterAgentResult:
    case_id: str
    policy_id: str
    decision: str
    reasons: list[str]
    derived: dict[str, float]
    next_actions: list[str]
    request_id: str


@dataclass(frozen=True)
class UnderwriteResult:
    decision: str
    risk_score: float
    model_id: str
    policy: dict[str, object]
    justification: Justification


def _build_evidence_query(payload: dict[str, object]) -> str:
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


def underwrite_case_with_justification(
    case_id: str,
    payload: dict[str, object],
    *,
    model_version: str | None = None,
    evidence_query: str | None = None,
    top_k: int = 5,
    request_id: str = "",
) -> UnderwriteResult:
    settings = get_settings()
    if settings.underwrite_engine == "legacy":
        return underwrite_case_with_justification_legacy(
            case_id,
            payload,
            model_version=model_version,
            evidence_query=evidence_query,
            top_k=top_k,
        )

    final_state = run_underwrite_graph(
        {
            "case_id": case_id,
            "payload": payload,
            "model_version": model_version,
            "top_k": top_k,
            "evidence_query": evidence_query,
            "request_id": request_id,
            "policy_result": {},
            "risk_score": 0.0,
            "model_id": "",
            "evidence_results": [],
            "justification": {},
            "decision": "review",
            "chunk_ids_used": [],
            "trace_events": [],
            "justifier_transcript": {},
        }
    )

    justification_payload = final_state["justification"]
    citations_payload = justification_payload.get("citations", [])
    citations = []
    if isinstance(citations_payload, list):
        for item in citations_payload:
            if isinstance(item, dict):
                from caseflow.domain.mortgage.justification import Citation

                citations.append(
                    Citation(
                        document_id=str(item.get("document_id", "")),
                        chunk_id=str(item.get("chunk_id", "")),
                        start_char=int(item.get("start_char", 0)),
                        end_char=int(item.get("end_char", 0)),
                        score=float(item.get("score", 0.0)),
                    )
                )

    policy = final_state["policy_result"]
    return UnderwriteResult(
        decision=str(final_state["decision"]),
        risk_score=float(final_state["risk_score"]),
        model_id=str(final_state["model_id"]),
        policy={
            "policy_id": str(policy.get("policy_id", "mortgage_v1")),
            "decision": str(policy.get("decision", "review")),
            "reasons": list(policy.get("reasons", [])),
            "derived": dict(policy.get("derived", {})),
        },
        justification=Justification(
            summary=str(justification_payload.get("summary", "")),
            reasons=list(justification_payload.get("reasons", [])),
            citations=citations,
        ),
    )


def underwrite_case_with_justification_legacy(
    case_id: str,
    payload: dict[str, object],
    *,
    model_version: str | None = None,
    evidence_query: str | None = None,
    top_k: int = 5,
) -> UnderwriteResult:
    policy_result = tool_policy_check(payload)
    risk_result: RiskScoreResult = tool_risk_score(payload, model_version)

    query = evidence_query.strip() if isinstance(evidence_query, str) else ""
    if not query:
        query = _build_evidence_query(payload)

    evidence = tool_evidence_search(case_id=case_id, query=query, top_k=top_k)
    justification = generate_deterministic_justification(
        decision=policy_result.decision,
        policy_reasons=policy_result.reasons,
        risk_score=risk_result.score,
        evidence_results=evidence,
    )

    return UnderwriteResult(
        decision=policy_result.decision,
        risk_score=risk_result.score,
        model_id=risk_result.model_id,
        policy={
            "policy_id": policy_result.policy_id,
            "decision": policy_result.decision,
            "reasons": policy_result.reasons,
            "derived": policy_result.derived,
        },
        justification=justification,
    )


class UnderwriterState(TypedDict):
    case_id: str
    features: dict[str, object]
    mortgage_decision: dict[str, object]
    next_actions: list[str]
    request_id: str


def _policy_check_node(state: UnderwriterState) -> UnderwriterState:
    decision = evaluate_mortgage_policy_v1({"features": state["features"]})
    return {
        **state,
        "mortgage_decision": {
            "policy_id": decision.policy_id,
            "decision": decision.decision,
            "reasons": decision.reasons,
            "derived": decision.derived,
        },
    }


def _plan_next_actions_node(state: UnderwriterState) -> UnderwriterState:
    mortgage_decision = state["mortgage_decision"]
    decision = str(mortgage_decision["decision"])

    if decision == "review":
        next_actions = [
            "REQUEST_PAYSTUB",
            "REQUEST_BANK_STATEMENTS",
            "RUN_RISK_SCORE",
            "RETRIEVE_POLICY_SNIPPETS",
        ]
    elif decision == "decline":
        next_actions = ["SEND_ADVERSE_ACTION_NOTICE"]
    else:
        next_actions = ["PREPARE_CONDITIONS_CHECKLIST"]

    return {**state, "next_actions": next_actions}


def build_underwriter_graph():
    graph = StateGraph(UnderwriterState)
    graph.add_node("policy_check", _policy_check_node)
    graph.add_node("plan_next_actions", _plan_next_actions_node)
    graph.add_edge(START, "policy_check")
    graph.add_edge("policy_check", "plan_next_actions")
    graph.set_finish_point("plan_next_actions")
    return graph.compile()


_graph = build_underwriter_graph()


def run_underwriter_agent(
    case: UnderwriterCase,
    request_id: str,
) -> UnderwriterAgentResult:
    logger.info(
        "underwriter_agent_started",
        extra={
            "event": "underwriter_agent_started",
            "case_id": case.case_id,
            "request_id": request_id,
        },
    )

    final_state = _graph.invoke(
        {
            "case_id": case.case_id,
            "features": case.features,
            "mortgage_decision": {},
            "next_actions": [],
            "request_id": request_id,
        }
    )

    mortgage_decision = final_state["mortgage_decision"]
    logger.info(
        "underwriter_policy_evaluated",
        extra={
            "event": "underwriter_policy_evaluated",
            "decision": mortgage_decision["decision"],
            "policy_id": mortgage_decision["policy_id"],
            "case_id": case.case_id,
            "request_id": request_id,
        },
    )
    logger.info(
        "underwriter_next_actions_planned",
        extra={
            "event": "underwriter_next_actions_planned",
            "next_actions": final_state["next_actions"],
            "case_id": case.case_id,
            "request_id": request_id,
        },
    )

    return UnderwriterAgentResult(
        case_id=case.case_id,
        policy_id=str(mortgage_decision["policy_id"]),
        decision=str(mortgage_decision["decision"]),
        reasons=list(mortgage_decision["reasons"]),
        derived=dict(mortgage_decision["derived"]),
        next_actions=list(final_state["next_actions"]),
        request_id=request_id,
    )
