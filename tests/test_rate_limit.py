from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.audit import clear_audit_sink_cache
from caseflow.core.rate_limit import clear_rate_limiter_cache
from caseflow.core.settings import clear_settings_cache
from caseflow.ml.registry import clear_active_model


def _reset_runtime_state() -> None:
    clear_settings_cache()
    clear_rate_limiter_cache()
    clear_audit_sink_cache()
    clear_active_model()


def test_rate_limit_disabled_allows_rapid_predict_calls(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    _reset_runtime_state()

    with TestClient(app) as client:
        responses = [
            client.post("/predict", json={"features": [0.1, -1.2, 2.3]})
            for _ in range(5)
        ]

    assert all(response.status_code == 200 for response in responses)


def test_rate_limit_enabled_returns_429_with_standard_envelope(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_RPS", "0")
    monkeypatch.setenv("RATE_LIMIT_BURST", "0")
    _reset_runtime_state()

    response = TestClient(app).post(
        "/decision",
        json={"features": [0.1, -1.2, 2.3]},
    )

    assert response.status_code == 429
    body = response.json()
    assert body == {
        "error": {
            "code": "http_error",
            "message": "Rate limit exceeded",
            "status": 429,
            "request_id": response.headers["X-Request-Id"],
        }
    }
