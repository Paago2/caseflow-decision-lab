import json
import logging

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.logging import JsonFormatter


def test_documents_intake_missing_loan_application_fields() -> None:
    payload = {
        "case_id": "case_123",
        "documents": [
            {"document_type": "paystub", "gross_monthly_income": 8500},
            {
                "document_type": "credit_summary",
                "credit_score": 705,
                "total_monthly_debt": 2200,
            },
            {"document_type": "property_valuation", "property_value": 450000},
        ],
    }

    response = TestClient(app).post("/documents/intake", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "case_123"
    assert body["extracted_features"] == {
        "gross_monthly_income": 8500.0,
        "total_monthly_debt": 2200.0,
        "credit_score": 705.0,
        "property_value": 450000.0,
    }
    assert body["missing"] == ["loan_amount", "occupancy"]
    assert body["source_summary"] == {
        "paystub": 1,
        "credit_summary": 1,
        "property_valuation": 1,
    }


def test_documents_intake_with_loan_application_has_no_missing() -> None:
    payload = {
        "case_id": "case_123",
        "documents": [
            {"document_type": "paystub", "gross_monthly_income": 9500},
            {
                "document_type": "credit_summary",
                "credit_score": 760,
                "total_monthly_debt": 2000,
            },
            {"document_type": "property_valuation", "property_value": 500000},
            {
                "document_type": "loan_application",
                "loan_amount": 300000,
                "occupancy": "primary",
            },
        ],
    }

    response = TestClient(app).post("/documents/intake", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["missing"] == []
    assert body["extracted_features"]["loan_amount"] == 300000.0
    assert body["extracted_features"]["occupancy"] == "primary"


def test_documents_decision_returns_422_when_required_missing() -> None:
    payload = {
        "case_id": "case_123",
        "documents": [
            {"document_type": "paystub", "gross_monthly_income": 8500},
            {
                "document_type": "credit_summary",
                "credit_score": 705,
                "total_monthly_debt": 2200,
            },
            {"document_type": "property_valuation", "property_value": 450000},
        ],
    }

    response = TestClient(app).post("/documents/decision", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert "loan_amount" in body["error"]["message"]
    assert "occupancy" in body["error"]["message"]


def test_documents_decision_deterministic_examples() -> None:
    client = TestClient(app)

    approve_payload = {
        "case_id": "case_approve",
        "documents": [
            {"document_type": "paystub", "gross_monthly_income": 10000},
            {
                "document_type": "credit_summary",
                "credit_score": 760,
                "total_monthly_debt": 3000,
            },
            {"document_type": "property_valuation", "property_value": 500000},
            {
                "document_type": "loan_application",
                "loan_amount": 300000,
                "occupancy": "primary",
            },
        ],
    }
    review_payload = {
        "case_id": "case_review",
        "documents": [
            {"document_type": "paystub", "gross_monthly_income": 10000},
            {
                "document_type": "credit_summary",
                "credit_score": 640,
                "total_monthly_debt": 3000,
            },
            {"document_type": "property_valuation", "property_value": 500000},
            {
                "document_type": "loan_application",
                "loan_amount": 300000,
                "occupancy": "secondary",
            },
        ],
    }
    decline_payload = {
        "case_id": "case_decline",
        "documents": [
            {"document_type": "paystub", "gross_monthly_income": 10000},
            {
                "document_type": "credit_summary",
                "credit_score": 500,
                "total_monthly_debt": 3000,
            },
            {"document_type": "property_valuation", "property_value": 500000},
            {
                "document_type": "loan_application",
                "loan_amount": 300000,
                "occupancy": "primary",
            },
        ],
    }

    approve_response = client.post("/documents/decision", json=approve_payload)
    review_response = client.post("/documents/decision", json=review_payload)
    decline_response = client.post("/documents/decision", json=decline_payload)

    assert approve_response.status_code == 200
    assert review_response.status_code == 200
    assert decline_response.status_code == 200

    assert approve_response.json()["decision"] == "approve"
    assert review_response.json()["decision"] == "review"
    assert decline_response.json()["decision"] == "decline"


def test_documents_intake_request_id_matches_header() -> None:
    payload = {
        "case_id": "case_123",
        "documents": [{"document_type": "paystub", "gross_monthly_income": 8500}],
    }

    response = TestClient(app).post(
        "/documents/intake",
        json=payload,
        headers={"X-Request-Id": "docs-request-id-1"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "docs-request-id-1"
    assert response.json()["request_id"] == "docs-request-id-1"


def test_documents_intake_emits_structured_log_event(caplog) -> None:
    caplog.set_level(logging.INFO)
    caplog.handler.setFormatter(JsonFormatter())

    payload = {
        "case_id": "case_123",
        "documents": [{"document_type": "paystub", "gross_monthly_income": 8500}],
    }
    response = TestClient(app).post("/documents/intake", json=payload)

    assert response.status_code == 200
    parsed = []
    for line in caplog.text.splitlines():
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    assert any(record.get("event") == "documents_intake_completed" for record in parsed)
