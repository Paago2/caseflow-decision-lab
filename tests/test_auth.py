from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_health_is_unprotected_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("APP_ENV", "dev")
    clear_settings_cache()

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_keeps_existing_behavior(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("APP_ENV", "dev")
    clear_settings_cache()

    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code in (200, 503)
    assert response.json()["status"] in ("ready", "not_ready")


def test_protected_ping_requires_api_key_header(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("APP_ENV", "dev")
    clear_settings_cache()

    client = TestClient(app)

    missing_header = client.get("/protected/ping")
    assert missing_header.status_code == 401
    assert missing_header.json() == {"detail": "Unauthorized"}

    wrong_header = client.get("/protected/ping", headers={"X-API-Key": "wrong-key"})
    assert wrong_header.status_code == 401
    assert wrong_header.json() == {"detail": "Unauthorized"}

    correct_header = client.get(
        "/protected/ping",
        headers={"X-API-Key": "server-key"},
    )
    assert correct_header.status_code == 200
    assert correct_header.json() == {"status": "ok"}
