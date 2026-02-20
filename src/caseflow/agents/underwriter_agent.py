from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import START, StateGraph

from caseflow.domain.mortgage.policy import evaluate_mortgage_policy_v1

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
