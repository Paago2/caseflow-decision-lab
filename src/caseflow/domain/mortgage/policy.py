from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MortgageDecision:
    policy_id: str
    decision: str
    reasons: list[str]
    derived: dict[str, float]


def evaluate_mortgage_policy_v1(payload: dict[str, object]) -> MortgageDecision:
    required_keys = {
        "credit_score",
        "monthly_income",
        "monthly_debt",
        "loan_amount",
        "property_value",
        "occupancy",
    }
    missing_keys = sorted(required_keys - set(payload.keys()))
    if missing_keys:
        raise ValueError("Missing required keys: " + ", ".join(missing_keys))

    try:
        credit_score = float(payload["credit_score"])
        monthly_income = float(payload["monthly_income"])
        monthly_debt = float(payload["monthly_debt"])
        loan_amount = float(payload["loan_amount"])
        property_value = float(payload["property_value"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Numeric mortgage features must be valid numbers") from exc

    occupancy_raw = payload["occupancy"]
    if not isinstance(occupancy_raw, str):
        raise ValueError("occupancy must be a string")
    occupancy = occupancy_raw.strip().lower()
    if occupancy not in {"primary", "secondary", "investment"}:
        raise ValueError("occupancy must be one of: primary, secondary, investment")

    dti = monthly_debt / monthly_income if monthly_income > 0 else 0.0
    ltv = loan_amount / property_value if property_value > 0 else 0.0

    decline_reasons: list[str] = []
    if monthly_income <= 0:
        decline_reasons.append("DECLINE_INCOME_INVALID")
    if property_value <= 0:
        decline_reasons.append("DECLINE_PROPERTY_VALUE_INVALID")
    if credit_score < 580:
        decline_reasons.append("DECLINE_CREDIT_TOO_LOW")
    if monthly_income > 0 and dti > 0.50:
        decline_reasons.append("DECLINE_DTI_TOO_HIGH")
    if property_value > 0 and ltv > 0.97:
        decline_reasons.append("DECLINE_LTV_TOO_HIGH")
    if occupancy == "investment" and credit_score < 620:
        decline_reasons.append("DECLINE_INVESTMENT_CREDIT_TOO_LOW")

    review_reasons: list[str] = []
    if 580 <= credit_score < 660:
        review_reasons.append("REVIEW_CREDIT_BORDERLINE")
    if monthly_income > 0 and 0.43 < dti <= 0.50:
        review_reasons.append("REVIEW_DTI_BORDERLINE")
    if property_value > 0 and 0.80 < ltv <= 0.97:
        review_reasons.append("REVIEW_LTV_BORDERLINE")
    if occupancy == "investment" and credit_score >= 620:
        review_reasons.append("REVIEW_INVESTMENT_LOAN")

    if decline_reasons:
        return MortgageDecision(
            policy_id="mortgage_v1",
            decision="decline",
            reasons=decline_reasons,
            derived={"dti": float(dti), "ltv": float(ltv)},
        )

    if review_reasons:
        return MortgageDecision(
            policy_id="mortgage_v1",
            decision="review",
            reasons=review_reasons,
            derived={"dti": float(dti), "ltv": float(ltv)},
        )

    return MortgageDecision(
        policy_id="mortgage_v1",
        decision="approve",
        reasons=["APPROVE_POLICY_V1"],
        derived={"dti": float(dti), "ltv": float(ltv)},
    )
