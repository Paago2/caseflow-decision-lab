import base64

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_evidence_stats_and_delete_lifecycle(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    client = TestClient(app)
    text = "Income verification and liabilities summary for case lifecycle tests."
    ocr = client.post(
        "/ocr/extract",
        json={
            "case_id": "case_life_1",
            "document": {
                "filename": "life.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        },
    )
    assert ocr.status_code == 200
    document_id = ocr.json()["document_id"]

    idx = client.post(
        "/mortgage/case_life_1/evidence/reindex",
        json={"documents": [{"document_id": document_id}]},
    )
    assert idx.status_code == 200

    stats = client.get("/mortgage/case_life_1/evidence/stats")
    assert stats.status_code == 200
    stats_body = stats.json()
    assert stats_body["num_chunks"] >= 1
    assert stats_body["documents"]
    assert stats_body["documents"][0]["document_id"] == document_id

    deleted = client.delete("/mortgage/case_life_1/evidence")
    assert deleted.status_code == 200
    assert deleted.json()["deleted_chunks"] >= 1

    search = client.get(
        "/mortgage/case_life_1/evidence/search",
        params={"q": "income", "top_k": 5},
    )
    assert search.status_code == 200
    assert search.json()["results"] == []
