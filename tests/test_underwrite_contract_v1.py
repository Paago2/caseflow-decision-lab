import base64

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_underwrite_contract_v1_schema_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("EVIDENCE_MIN_SCORE", "0.0")
    clear_settings_cache()

    client = TestClient(app)
    text = "contract v1 evidence"
    ocr = client.post(
        "/ocr/extract",
        json={
            "case_id": "case_contract_v1",
            "document": {
                "filename": "contract.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        },
    )
    assert ocr.status_code == 200
    document_id = ocr.json()["document_id"]
    reindex = client.post(
        "/mortgage/case_contract_v1/evidence/reindex",
        json={"documents": [{"document_id": document_id}]},
    )
    assert reindex.status_code == 200

    response = client.post(
        "/mortgage/case_contract_v1/underwrite",
        json={
            "payload": {
                "credit_score": 710,
                "monthly_income": 9000,
                "monthly_debt": 2600,
                "loan_amount": 280000,
                "property_value": 450000,
                "occupancy": "primary",
            }
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["schema_version"] == "v1"
    expected_top_level = {
        "schema_version",
        "case_id",
        "decision",
        "risk_score",
        "policy",
        "justification",
        "request_id",
    }
    assert expected_top_level.issubset(set(body.keys()))

    assert isinstance(body["policy"], dict)
    assert {"policy_id", "decision", "reasons", "derived"}.issubset(
        set(body["policy"].keys())
    )
    assert isinstance(body["justification"], dict)
    assert {"summary", "reasons", "citations"}.issubset(
        set(body["justification"].keys())
    )
