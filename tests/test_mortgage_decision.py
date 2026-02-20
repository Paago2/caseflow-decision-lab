import json
from pathlib import Path

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.audit import clear_audit_sink_cache
from caseflow.core.settings import clear_settings_cache


def _reset_state() -> None:
    clear_settings_cache()
    clear_audit_sink_cache()


def test_mortgage_decision_approve_path(monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_SINK", "log")
    _reset_state()

    payload = {
        "features": {
            "credit_score": 760,
            "monthly_income": 10000,
            "monthly_debt": 3000,
            "loan_amount": 300000,
            "property_value": 500000,
            "occupancy": "primary",
        }
    }
    response = TestClient(app).post("/mortgage/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["policy_id"] == "mortgage_v1"
    assert body["decision"] == "approve"
    assert body["reasons"] == ["APPROVE_POLICY_V1"]


def test_mortgage_decision_decline_income_invalid(monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_SINK", "log")
    _reset_state()

    payload = {
        "features": {
            "credit_score": 760,
            "monthly_income": 0,
            "monthly_debt": 1000,
            "loan_amount": 200000,
            "property_value": 300000,
            "occupancy": "primary",
        }
    }
    response = TestClient(app).post("/mortgage/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "decline"
    assert "DECLINE_INCOME_INVALID" in body["reasons"]


def test_mortgage_decision_decline_credit_too_low(monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_SINK", "log")
    _reset_state()

    payload = {
        "features": {
            "credit_score": 500,
            "monthly_income": 10000,
            "monthly_debt": 3000,
            "loan_amount": 200000,
            "property_value": 300000,
            "occupancy": "primary",
        }
    }
    response = TestClient(app).post("/mortgage/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "decline"
    assert "DECLINE_CREDIT_TOO_LOW" in body["reasons"]


def test_mortgage_decision_review_borderline_credit(monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_SINK", "log")
    _reset_state()

    payload = {
        "features": {
            "credit_score": 640,
            "monthly_income": 10000,
            "monthly_debt": 3000,
            "loan_amount": 200000,
            "property_value": 300000,
            "occupancy": "secondary",
        }
    }
    response = TestClient(app).post("/mortgage/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "review"
    assert "REVIEW_CREDIT_BORDERLINE" in body["reasons"]


def test_mortgage_decision_review_borderline_ltv(monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_SINK", "log")
    _reset_state()

    payload = {
        "features": {
            "credit_score": 720,
            "monthly_income": 10000,
            "monthly_debt": 3000,
            "loan_amount": 430000,
            "property_value": 500000,
            "occupancy": "primary",
        }
    }
    response = TestClient(app).post("/mortgage/decision", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "review"
    assert "REVIEW_LTV_BORDERLINE" in body["reasons"]


def test_mortgage_decision_occupancy_validation_returns_422(monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_SINK", "log")
    _reset_state()

    payload = {
        "features": {
            "credit_score": 720,
            "monthly_income": 10000,
            "monthly_debt": 3000,
            "loan_amount": 200000,
            "property_value": 300000,
            "occupancy": "vacation",
        }
    }
    response = TestClient(app).post("/mortgage/decision", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "http_error"


def test_mortgage_decision_missing_key_returns_422(monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_SINK", "log")
    _reset_state()

    payload = {
        "features": {
            "credit_score": 720,
            "monthly_income": 10000,
            "monthly_debt": 3000,
            "loan_amount": 200000,
            "property_value": 300000,
            # missing occupancy
        }
    }
    response = TestClient(app).post("/mortgage/decision", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "http_error"


def test_mortgage_decision_audit_jsonl_writes_one_line(
    monkeypatch, tmp_path: Path
) -> None:
    sink_path = tmp_path / "mortgage_events.jsonl"
    monkeypatch.setenv("AUDIT_SINK", "jsonl")
    monkeypatch.setenv("AUDIT_JSONL_PATH", str(sink_path))
    _reset_state()

    payload = {
        "features": {
            "credit_score": 760,
            "monthly_income": 10000,
            "monthly_debt": 3000,
            "loan_amount": 300000,
            "property_value": 500000,
            "occupancy": "primary",
        }
    }
    response = TestClient(app).post("/mortgage/decision", json=payload)

    assert response.status_code == 200
    lines = sink_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload_line = json.loads(lines[0])
    assert payload_line["policy_id"] == "mortgage_v1"
    assert "derived" in payload_line
