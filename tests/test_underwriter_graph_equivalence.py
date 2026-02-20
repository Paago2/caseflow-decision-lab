import base64

from fastapi.testclient import TestClient

from caseflow.agents.underwriter_agent import (
    underwrite_case_with_justification,
    underwrite_case_with_justification_legacy,
)
from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_underwriter_graph_matches_legacy_core_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    monkeypatch.setenv("EVIDENCE_MIN_SCORE", "0.0")
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    client = TestClient(app)
    text = "Equivalence test evidence for income and liabilities."
    ocr = client.post(
        "/ocr/extract",
        json={
            "case_id": "case_graph_eq",
            "document": {
                "filename": "eq.txt",
                "content_type": "text/plain",
                "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            },
        },
    )
    assert ocr.status_code == 200
    document_id = ocr.json()["document_id"]

    reindex = client.post(
        "/mortgage/case_graph_eq/evidence/reindex",
        json={"documents": [{"document_id": document_id}]},
    )
    assert reindex.status_code == 200

    payload = {
        "credit_score": 710,
        "monthly_income": 9000,
        "monthly_debt": 2600,
        "loan_amount": 280000,
        "property_value": 450000,
        "occupancy": "primary",
    }

    graph_result = underwrite_case_with_justification("case_graph_eq", payload, top_k=5)
    legacy_result = underwrite_case_with_justification_legacy(
        "case_graph_eq", payload, top_k=5
    )

    assert graph_result.decision == legacy_result.decision
    assert graph_result.risk_score == legacy_result.risk_score
    assert graph_result.policy == legacy_result.policy
    assert [c.chunk_id for c in graph_result.justification.citations] == [
        c.chunk_id for c in legacy_result.justification.citations
    ]
