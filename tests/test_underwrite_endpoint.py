import base64

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_underwrite_endpoint_returns_citations_in_stable_order(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    client = TestClient(app)
    content = (
        "Borrower income verification appears stable with payroll records and "
        "ongoing employment statements."
    )
    ocr_response = client.post(
        "/ocr/extract",
        json={
            "case_id": "case_uw_1",
            "document": {
                "filename": "income.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(content.encode("utf-8")).decode(
                    "ascii"
                ),
            },
        },
    )
    assert ocr_response.status_code == 200
    document_id = ocr_response.json()["document_id"]

    index_response = client.post(
        "/mortgage/case_uw_1/evidence/index",
        json={"documents": [{"document_id": document_id}], "overwrite": True},
    )
    assert index_response.status_code == 200

    underwrite_payload = {
        "payload": {
            "credit_score": 710,
            "monthly_income": 9000,
            "monthly_debt": 2600,
            "loan_amount": 280000,
            "property_value": 450000,
            "occupancy": "primary",
        },
        "top_k": 5,
    }
    response = client.post("/mortgage/case_uw_1/underwrite", json=underwrite_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "case_uw_1"
    assert body["justification"]["citations"]
    citations = body["justification"]["citations"]
    assert citations[0]["document_id"] == document_id
    assert all("C1" in body["justification"]["reasons"][i] for i in [0, 1])

    second = client.post("/mortgage/case_uw_1/underwrite", json=underwrite_payload)
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["justification"]["citations"] == citations
    assert second_body["justification"]["reasons"] == body["justification"]["reasons"]
