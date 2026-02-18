from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache
from caseflow.ml.registry import clear_active_model


def test_ready_when_api_key_set_and_app_env_valid(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "dev")
    clear_settings_cache()

    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "env_loaded": True,
            "api_key_set": True,
            "app_env_valid": True,
            "model_loaded": True,
        },
    }


def test_not_ready_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "local")
    clear_settings_cache()

    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "env_loaded": True,
            "api_key_set": False,
            "app_env_valid": True,
            "model_loaded": True,
        },
        "reason": "api_key_not_set",
    }


def test_not_ready_when_active_model_fails_to_load(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("MODEL_REGISTRY_DIR", str(tmp_path / "missing-registry"))
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v1")
    clear_settings_cache()
    clear_active_model()

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"] == {
        "env_loaded": True,
        "api_key_set": True,
        "app_env_valid": True,
        "model_loaded": False,
    }
    assert isinstance(body.get("reason"), str)
    assert body["reason"].startswith("model_not_loaded")
