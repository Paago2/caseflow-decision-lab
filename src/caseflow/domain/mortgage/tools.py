from __future__ import annotations

from dataclasses import dataclass

from caseflow.domain.mortgage.policy import (
    MortgageDecision,
    evaluate_mortgage_policy_v1,
)
from caseflow.ml.registry import get_active_model, load_model
from caseflow.ml.vector_store import FileVectorStore, SearchResult


@dataclass(frozen=True)
class RiskScoreResult:
    model_id: str
    score: float


def tool_policy_check(case_payload: dict[str, object]) -> MortgageDecision:
    return evaluate_mortgage_policy_v1({"features": case_payload})


def _mortgage_vector_from_payload(payload: dict[str, object]) -> list[float]:
    try:
        credit_score = float(payload["credit_score"])
        monthly_income = float(payload["monthly_income"])
        monthly_debt = float(payload["monthly_debt"])
        loan_amount = float(payload["loan_amount"])
        property_value = float(payload["property_value"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Risk scoring requires mortgage numeric fields: credit_score, "
            "monthly_income, monthly_debt, loan_amount, property_value"
        ) from exc

    dti = monthly_debt / monthly_income if monthly_income > 0 else 0.0
    ltv = loan_amount / property_value if property_value > 0 else 0.0
    return [credit_score / 850.0, dti, ltv]


def _named_model_vector_from_payload(
    payload: dict[str, object],
    feature_names: list[str],
) -> list[float]:
    base_vector = _mortgage_vector_from_payload(payload)
    credit_ratio, dti, ltv = base_vector
    mapped: dict[str, float] = {
        "age": credit_ratio,
        "sex": 0.0,
        "bmi": dti,
        "bp": ltv,
        "s1": credit_ratio,
        "s2": dti,
        "s3": ltv,
        "s4": credit_ratio,
        "s5": dti,
        "s6": ltv,
    }
    return [mapped.get(name, 0.0) for name in feature_names]


def tool_risk_score(
    case_payload: dict[str, object], model_version: str | None
) -> RiskScoreResult:
    model = load_model(model_version) if model_version else get_active_model()

    if model.feature_names is not None:
        vector = _named_model_vector_from_payload(case_payload, model.feature_names)
    else:
        vector = _mortgage_vector_from_payload(case_payload)

    try:
        score = model.predict(vector)
    except ValueError as exc:
        raise ValueError(
            f"Unable to score payload with model '{model.model_id}'"
        ) from exc

    return RiskScoreResult(model_id=model.model_id, score=score)


def tool_evidence_search(
    case_id: str,
    query: str,
    top_k: int = 5,
) -> list[SearchResult]:
    return FileVectorStore().search(query=query, top_k=top_k, case_id=case_id)
