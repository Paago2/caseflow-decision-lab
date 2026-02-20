import base64

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def _ingest_and_index(client: TestClient, case_id: str, text: str) -> str:
    ocr = client.post(
        "/ocr/extract",
        json={
            "case_id": case_id,
            "document": {
                "filename": f"{case_id}.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        },
    )
    assert ocr.status_code == 200
    document_id = ocr.json()["document_id"]
    idx = client.post(
        f"/mortgage/{case_id}/evidence/index",
        json={"documents": [{"document_id": document_id}], "overwrite": True},
    )
    assert idx.status_code == 200
    return document_id


def test_case_isolation_search_does_not_leak_between_cases(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    client = TestClient(app)
    doc_a = _ingest_and_index(client, "case_iso_a", "alpha income payroll evidence")
    _ingest_and_index(client, "case_iso_b", "beta collateral and appraisal evidence")

    search_a = client.get(
        "/mortgage/case_iso_a/evidence/search",
        params={"q": "evidence", "top_k": 10},
    )
    assert search_a.status_code == 200
    results = search_a.json()["results"]
    assert results
    assert all(item["document_id"] == doc_a for item in results)
