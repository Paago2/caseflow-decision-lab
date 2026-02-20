import base64

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_trace_capture_and_retrieval(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("TRACE_ENABLED", "true")
    monkeypatch.setenv("EVIDENCE_MIN_SCORE", "0.0")
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    client = TestClient(app)
    text = "trace capture evidence text"
    ocr = client.post(
        "/ocr/extract",
        json={
            "case_id": "case_trace_1",
            "document": {
                "filename": "trace.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        },
    )
    assert ocr.status_code == 200
    document_id = ocr.json()["document_id"]
    reindex = client.post(
        "/mortgage/case_trace_1/evidence/reindex",
        json={"documents": [{"document_id": document_id}]},
    )
    assert reindex.status_code == 200

    response = client.post(
        "/mortgage/case_trace_1/underwrite",
        headers={"X-Request-Id": "trace-req-1"},
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

    trace = client.get(
        "/mortgage/case_trace_1/underwrite/trace",
        params={"request_id": "trace-req-1"},
    )
    assert trace.status_code == 200
    body = trace.json()["trace"]
    nodes = [item["node_name"] for item in body["trace"]]
    assert nodes == [
        "policy",
        "risk",
        "build_query",
        "evidence",
        "justify",
        "decide",
        "audit_metrics",
    ]

    evidence_events = [
        item for item in body["trace"] if item["node_name"] == "evidence"
    ]
    assert evidence_events
    outputs = evidence_events[0]["outputs"]
    assert "chunk_ids" in outputs
    assert "text" not in str(body)
