import base64

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_evidence_min_score_threshold_filters_results(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("EVIDENCE_MIN_SCORE", "1.1")
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    client = TestClient(app)
    text = "Income and payroll records with stable employment history."
    ocr = client.post(
        "/ocr/extract",
        json={
            "case_id": "case_thresh_1",
            "document": {
                "filename": "thresh.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        },
    )
    assert ocr.status_code == 200
    document_id = ocr.json()["document_id"]

    index_resp = client.post(
        "/mortgage/case_thresh_1/evidence/index",
        json={"documents": [{"document_id": document_id}], "overwrite": True},
    )
    assert index_resp.status_code == 200

    search = client.get(
        "/mortgage/case_thresh_1/evidence/search",
        params={"q": "income", "top_k": 5},
    )
    assert search.status_code == 200
    body = search.json()
    assert body["results"] == []
    assert body["min_score"] == 1.1
