import json
from pathlib import Path

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.audit import clear_audit_sink_cache
from caseflow.core.settings import clear_settings_cache
from caseflow.ml.registry import clear_active_model


def _reset_runtime_state() -> None:
    clear_settings_cache()
    clear_audit_sink_cache()
    clear_active_model()


def test_decision_writes_jsonl_audit_event(monkeypatch, tmp_path: Path) -> None:
    sink_path = tmp_path / "decision_events.jsonl"

    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("AUDIT_SINK", "jsonl")
    monkeypatch.setenv("AUDIT_JSONL_PATH", str(sink_path))
    _reset_runtime_state()

    response = TestClient(app).post(
        "/decision",
        json={"features": [0.1, -1.2, 2.3]},
    )

    assert response.status_code == 200
    assert sink_path.is_file()

    lines = sink_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    payload = json.loads(lines[0])
    assert payload["request_id"] == response.json()["request_id"]
    assert payload["model_id"] == response.json()["model_id"]
    assert payload["decision"] == response.json()["decision"]
    assert isinstance(payload["score"], float)
    assert isinstance(payload["reasons"], list)
    assert isinstance(payload["timestamp"], str)


def test_decision_audit_failure_does_not_break_response(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("AUDIT_SINK", "log")
    _reset_runtime_state()

    class _FailingSink:
        def emit_decision_event(self, event: dict) -> None:
            raise RuntimeError("sink failed")

    monkeypatch.setattr(
        "caseflow.api.routes_decision.get_audit_sink",
        lambda: _FailingSink(),
    )

    response = TestClient(app).post(
        "/decision",
        json={"features": [0.1, -1.2, 2.3]},
    )

    assert response.status_code == 200
    body = response.json()
    assert "decision" in body
    assert "request_id" in body
