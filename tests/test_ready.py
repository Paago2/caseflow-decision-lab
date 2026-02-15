from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


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
        },
    }


def test_not_ready_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "prod")
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
        },
    }
