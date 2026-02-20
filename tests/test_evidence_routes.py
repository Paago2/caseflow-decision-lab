import base64

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_evidence_index_and_search_routes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    client = TestClient(app)
    source_text = "Borrower income verification from payroll statement."
    ocr_payload = {
        "case_id": "case_route_1",
        "document": {
            "filename": "paystub.txt",
            "content_type": "text/plain",
            "content_b64": base64.b64encode(source_text.encode("utf-8")).decode(
                "ascii"
            ),
        },
    }
    ocr_response = client.post("/ocr/extract", json=ocr_payload)
    assert ocr_response.status_code == 200
    document_id = ocr_response.json()["document_id"]

    index_payload = {
        "documents": [{"document_id": document_id}],
        "overwrite": True,
    }
    index_response = client.post(
        "/mortgage/case_route_1/evidence/index", json=index_payload
    )
    assert index_response.status_code == 200
    index_body = index_response.json()
    assert index_body["indexed_chunks"] >= 1

    search_response = client.get(
        "/mortgage/case_route_1/evidence/search",
        params={"q": "income verification", "top_k": 5},
    )
    assert search_response.status_code == 200
    search_body = search_response.json()
    assert search_body["case_id"] == "case_route_1"
    assert search_body["results"]
    first = search_body["results"][0]
    assert first["document_id"] == document_id
    assert "income" in first["text"].lower()
