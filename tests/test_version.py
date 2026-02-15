from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_version_unprotected_and_defaults(monkeypatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("BUILD_TIME", raising=False)
    clear_settings_cache()

    client = TestClient(app)
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "app_name": "caseflow-decision-lab",
        "app_env": "local",
        "version": "0.1.0",
        "git_sha": "unknown",
        "build_time": "unknown",
    }


def test_version_returns_overridden_env_values_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "caseflow-custom")
    monkeypatch.setenv("APP_ENV", "stg")
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    monkeypatch.setenv("GIT_SHA", "abc123def")
    monkeypatch.setenv("BUILD_TIME", "2026-02-15T14:00:00Z")
    clear_settings_cache()

    client = TestClient(app)
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "app_name": "caseflow-custom",
        "app_env": "stg",
        "version": "1.2.3",
        "git_sha": "abc123def",
        "build_time": "2026-02-15T14:00:00Z",
    }