import base64

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.metrics import clear_metrics
from caseflow.core.settings import clear_settings_cache


def test_evidence_and_underwrite_metrics_emit(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()
    clear_metrics()

    client = TestClient(app)
    text = "income verification metrics evidence"
    ocr = client.post(
        "/ocr/extract",
        json={
            "case_id": "case_metrics_1",
            "document": {
                "filename": "metrics.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        },
    )
    assert ocr.status_code == 200
    document_id = ocr.json()["document_id"]

    reindex = client.post(
        "/mortgage/case_metrics_1/evidence/reindex",
        json={"documents": [{"document_id": document_id}]},
    )
    assert reindex.status_code == 200

    search = client.get(
        "/mortgage/case_metrics_1/evidence/search",
        params={"q": "income", "top_k": 5},
    )
    assert search.status_code == 200

    underwrite = client.post(
        "/mortgage/case_metrics_1/underwrite",
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
    assert underwrite.status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert "evidence_index_requests_total" in body
    assert "evidence_index_chunks_total" in body
    assert "evidence_search_requests_total" in body
    assert "evidence_search_latency_ms_count" in body
    assert "evidence_search_top_score" in body
    assert "underwrite_citations_total" in body
