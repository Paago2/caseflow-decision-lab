from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_underwrite_replay_matches_original_key_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("UNDERWRITE_PERSIST_RESULTS", "true")
    monkeypatch.setenv("UNDERWRITE_RESULTS_DIR", str(tmp_path / "underwrite_results"))
    monkeypatch.setenv("EVIDENCE_INDEX_DIR", str(tmp_path / "evidence_index"))
    clear_settings_cache()

    client = TestClient(app)
    original = client.post(
        "/mortgage/case_replay_1/underwrite",
        headers={"X-Request-Id": "replay-req-1"},
        json={
            "payload": {
                "credit_score": 680,
                "monthly_income": 8000,
                "monthly_debt": 2500,
                "loan_amount": 250000,
                "property_value": 400000,
                "occupancy": "primary",
            }
        },
    )
    assert original.status_code == 200

    replay = client.post(
        "/mortgage/case_replay_1/underwrite/replay",
        params={"request_id": "replay-req-1"},
    )
    assert replay.status_code == 200

    original_body = original.json()
    replay_body = replay.json()
    assert replay_body["schema_version"] == "v1"
    assert replay_body["decision"] == original_body["decision"]
    assert replay_body["risk_score"] == original_body["risk_score"]
    assert [item["chunk_id"] for item in replay_body["justification"]["citations"]] == [
        item["chunk_id"] for item in original_body["justification"]["citations"]
    ]
