import base64

from fastapi.testclient import TestClient

from caseflow.agents.underwriter_graph import run_underwrite_graph
from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_underwriter_graph_is_deterministic(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("EVIDENCE_MIN_SCORE", "0.0")
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    client = TestClient(app)
    text = "Deterministic income and employment evidence for graph tests."
    ocr = client.post(
        "/ocr/extract",
        json={
            "case_id": "case_graph_det",
            "document": {
                "filename": "graph.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        },
    )
    assert ocr.status_code == 200
    document_id = ocr.json()["document_id"]

    reindex = client.post(
        "/mortgage/case_graph_det/evidence/reindex",
        json={"documents": [{"document_id": document_id}]},
    )
    assert reindex.status_code == 200

    state = {
        "case_id": "case_graph_det",
        "payload": {
            "credit_score": 710,
            "monthly_income": 9000,
            "monthly_debt": 2600,
            "loan_amount": 280000,
            "property_value": 450000,
            "occupancy": "primary",
        },
        "model_version": None,
        "top_k": 5,
        "evidence_query": None,
        "request_id": "req-graph-det",
        "policy_result": {},
        "risk_score": 0.0,
        "model_id": "",
        "evidence_results": [],
        "justification": {},
        "decision": "review",
        "chunk_ids_used": [],
    }

    out_a = run_underwrite_graph(state)
    out_b = run_underwrite_graph(state)

    assert out_a["decision"] == out_b["decision"]
    assert out_a["risk_score"] == out_b["risk_score"]
    assert out_a["justification"] == out_b["justification"]
    assert out_a["chunk_ids_used"] == out_b["chunk_ids_used"]
