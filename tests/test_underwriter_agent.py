import json
import logging

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.logging import JsonFormatter


def _payload(
    *,
    credit_score: float,
    monthly_income: float,
    monthly_debt: float,
    loan_amount: float,
    property_value: float,
    occupancy: str,
) -> dict[str, object]:
    return {
        "case_id": "case-001",
        "features": {
            "credit_score": credit_score,
            "monthly_income": monthly_income,
            "monthly_debt": monthly_debt,
            "loan_amount": loan_amount,
            "property_value": property_value,
            "occupancy": occupancy,
        },
    }


def test_underwriter_run_approve_has_prepare_conditions_action() -> None:
    response = TestClient(app).post(
        "/underwriter/run",
        json=_payload(
            credit_score=760,
            monthly_income=10000,
            monthly_debt=3000,
            loan_amount=250000,
            property_value=500000,
            occupancy="primary",
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "approve"
    assert "PREPARE_CONDITIONS_CHECKLIST" in body["next_actions"]


def test_underwriter_run_review_has_expected_actions() -> None:
    response = TestClient(app).post(
        "/underwriter/run",
        json=_payload(
            credit_score=640,
            monthly_income=10000,
            monthly_debt=3000,
            loan_amount=300000,
            property_value=500000,
            occupancy="secondary",
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "review"
    assert "REQUEST_PAYSTUB" in body["next_actions"]
    assert "RUN_RISK_SCORE" in body["next_actions"]


def test_underwriter_run_decline_has_adverse_action_notice() -> None:
    response = TestClient(app).post(
        "/underwriter/run",
        json=_payload(
            credit_score=500,
            monthly_income=10000,
            monthly_debt=3000,
            loan_amount=250000,
            property_value=500000,
            occupancy="primary",
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "decline"
    assert body["next_actions"] == ["SEND_ADVERSE_ACTION_NOTICE"]


def test_underwriter_run_propagates_request_id_from_header() -> None:
    response = TestClient(app).post(
        "/underwriter/run",
        headers={"X-Request-Id": "uw-req-id"},
        json=_payload(
            credit_score=760,
            monthly_income=10000,
            monthly_debt=3000,
            loan_amount=250000,
            property_value=500000,
            occupancy="primary",
        ),
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "uw-req-id"
    assert response.json()["request_id"] == "uw-req-id"


def test_underwriter_run_emits_started_log_event(caplog) -> None:
    caplog.set_level(logging.INFO)
    caplog.handler.setFormatter(JsonFormatter())

    response = TestClient(app).post(
        "/underwriter/run",
        headers={"X-Request-Id": "uw-log-id"},
        json=_payload(
            credit_score=760,
            monthly_income=10000,
            monthly_debt=3000,
            loan_amount=250000,
            property_value=500000,
            occupancy="primary",
        ),
    )
    assert response.status_code == 200

    parsed_records: list[dict[str, object]] = []
    for line in caplog.text.splitlines():
        try:
            parsed_records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    events = [record.get("event") for record in parsed_records]
    assert "underwriter_agent_started" in events
