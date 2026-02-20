from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache
from caseflow.domain.mortgage.underwrite_result import load_underwrite_result


def test_underwrite_result_persisted_when_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("UNDERWRITE_PERSIST_RESULTS", "true")
    monkeypatch.setenv("UNDERWRITE_RESULTS_DIR", str(tmp_path / "underwrite_results"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    clear_settings_cache()

    client = TestClient(app)
    response = client.post(
        "/mortgage/case_persist_1/underwrite",
        headers={"X-Request-Id": "persist-req-1"},
        json={
            "payload": {
                "credit_score": 680,
                "monthly_income": 8000,
                "monthly_debt": 2500,
                "loan_amount": 250000,
                "property_value": 400000,
                "occupancy": "primary",
            }
        },
    )
    assert response.status_code == 200

    stored = load_underwrite_result("case_persist_1", "persist-req-1")
    assert stored.case_id == "case_persist_1"
    assert stored.request_id == "persist-req-1"
    assert stored.schema_version == "v1"
