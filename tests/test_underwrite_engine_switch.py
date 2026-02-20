import base64

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_underwrite_engine_switch_graph_and_legacy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("EVIDENCE_MIN_SCORE", "0.0")
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    client = TestClient(app)
    text = "engine switch evidence text"
    ocr = client.post(
        "/ocr/extract",
        json={
            "case_id": "case_engine_1",
            "document": {
                "filename": "engine.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        },
    )
    assert ocr.status_code == 200
    document_id = ocr.json()["document_id"]
    reindex = client.post(
        "/mortgage/case_engine_1/evidence/reindex",
        json={"documents": [{"document_id": document_id}]},
    )
    assert reindex.status_code == 200

    payload = {
        "payload": {
            "credit_score": 700,
            "monthly_income": 8500,
            "monthly_debt": 2400,
            "loan_amount": 260000,
            "property_value": 420000,
            "occupancy": "primary",
        }
    }

    monkeypatch.setenv("UNDERWRITE_ENGINE", "graph")
    clear_settings_cache()
    graph_resp = client.post("/mortgage/case_engine_1/underwrite", json=payload)
    assert graph_resp.status_code == 200

    monkeypatch.setenv("UNDERWRITE_ENGINE", "legacy")
    clear_settings_cache()
    legacy_resp = client.post("/mortgage/case_engine_1/underwrite", json=payload)
    assert legacy_resp.status_code == 200

    assert graph_resp.json()["decision"] == legacy_resp.json()["decision"]
