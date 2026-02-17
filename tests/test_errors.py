from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache


def test_unhandled_exception_returns_standardized_500_with_request_id() -> None:
    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers.get("X-Request-Id")
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal Server Error",
            "status": 500,
            "request_id": response.headers["X-Request-Id"],
        }
    }


def test_protected_ping_401_uses_standardized_error_schema(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("APP_ENV", "dev")
    clear_settings_cache()

    client = TestClient(app)
    response = client.get("/protected/ping")

    assert response.status_code == 401
    assert response.headers.get("X-Request-Id")
    assert response.json() == {
        "error": {
            "code": "http_error",
            "message": "Unauthorized",
            "status": 401,
            "request_id": response.headers["X-Request-Id"],
        }
    }
