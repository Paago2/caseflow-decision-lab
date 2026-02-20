import base64

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_justifier_provider_switch_deterministic_and_stub(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("EVIDENCE_MIN_SCORE", "0.0")
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    client = TestClient(app)
    text = "provider switch evidence"
    ocr = client.post(
        "/ocr/extract",
        json={
            "case_id": "case_provider_1",
            "document": {
                "filename": "provider.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        },
    )
    assert ocr.status_code == 200
    document_id = ocr.json()["document_id"]
    reindex = client.post(
        "/mortgage/case_provider_1/evidence/reindex",
        json={"documents": [{"document_id": document_id}]},
    )
    assert reindex.status_code == 200

    payload = {
        "payload": {
            "credit_score": 710,
            "monthly_income": 9000,
            "monthly_debt": 2600,
            "loan_amount": 280000,
            "property_value": 450000,
            "occupancy": "primary",
        }
    }

    monkeypatch.setenv("JUSTIFIER_PROVIDER", "deterministic")
    clear_settings_cache()
    deterministic = client.post("/mortgage/case_provider_1/underwrite", json=payload)
    assert deterministic.status_code == 200

    monkeypatch.setenv("JUSTIFIER_PROVIDER", "stub_llm")
    clear_settings_cache()
    stub = client.post("/mortgage/case_provider_1/underwrite", json=payload)
    assert stub.status_code == 200

    d_body = deterministic.json()
    s_body = stub.json()
    assert isinstance(d_body["justification"]["citations"], list)
    assert isinstance(s_body["justification"]["citations"], list)

    stub_again = client.post("/mortgage/case_provider_1/underwrite", json=payload)
    assert stub_again.status_code == 200
    assert stub_again.json()["justification"] == s_body["justification"]
