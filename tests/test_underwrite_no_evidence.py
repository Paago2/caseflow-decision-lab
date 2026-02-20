from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_underwrite_without_evidence_returns_empty_citations(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    clear_settings_cache()

    payload = {
        "payload": {
            "credit_score": 680,
            "monthly_income": 8000,
            "monthly_debt": 2500,
            "loan_amount": 250000,
            "property_value": 400000,
            "occupancy": "primary",
        }
    }

    response = TestClient(app).post("/mortgage/case_none/underwrite", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["justification"]["citations"] == []
    assert (
        "No supporting evidence indexed for this case."
        in body["justification"]["summary"]
    )
