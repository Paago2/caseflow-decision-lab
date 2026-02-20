from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.policy import (
    HIGH_DTI,
    HIGH_LTV,
    LOW_CREDIT_SCORE,
    clear_policy_cache,
    evaluate_policy,
    load_policy,
)


def test_evaluate_policy_approve_path() -> None:
    clear_policy_cache()
    decision, reasons = evaluate_policy(
        {
            "credit_score": 740,
            "ltv": 0.75,
            "dti": 0.35,
        }
    )

    assert decision == "approve"
    assert reasons == []


def test_evaluate_policy_review_path_reasons_are_deterministic() -> None:
    clear_policy_cache()
    decision, reasons = evaluate_policy(
        {
            "credit_score": 690,
            "ltv": 0.82,
            "dti": 0.44,
        }
    )

    assert decision == "review"
    assert reasons == [LOW_CREDIT_SCORE, HIGH_LTV, HIGH_DTI]


def test_evaluate_policy_decline_path_reasons_are_deterministic() -> None:
    clear_policy_cache()
    decision, reasons = evaluate_policy(
        {
            "credit_score": 600,
            "ltv": 0.95,
            "dti": 0.60,
        }
    )

    assert decision == "decline"
    assert reasons == [LOW_CREDIT_SCORE, HIGH_LTV, HIGH_DTI]


def test_decision_response_includes_policy_version() -> None:
    clear_policy_cache()
    policy = load_policy()

    response = TestClient(app).post(
        "/decision",
        json={"features": [0.1, -1.2, 2.3]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["policy_version"] == policy["policy_version"]
