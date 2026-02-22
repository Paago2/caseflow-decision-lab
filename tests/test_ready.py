from fastapi.testclient import TestClient

from caseflow.api import routes_ready
from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache
from caseflow.ml.registry import clear_active_model


def _mock_all_infra_ok(monkeypatch) -> None:
    monkeypatch.setattr(routes_ready, "check_postgres", lambda _: (True, None))
    monkeypatch.setattr(routes_ready, "check_redis", lambda _: (True, None))
    monkeypatch.setattr(routes_ready, "check_minio", lambda _: (True, None))


def test_ready_when_infra_and_model_and_settings_ok(monkeypatch) -> None:
    _mock_all_infra_ok(monkeypatch)
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
            "postgres_ok": True,
            "redis_ok": True,
            "minio_ok": True,
            "model_loaded": True,
        },
    }


def test_not_ready_when_postgres_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        routes_ready, "check_postgres", lambda _: (False, "connection refused")
    )
    monkeypatch.setattr(routes_ready, "check_redis", lambda _: (True, None))
    monkeypatch.setattr(routes_ready, "check_minio", lambda _: (True, None))

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "dev")
    clear_settings_cache()

    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "env_loaded": True,
            "api_key_set": True,
            "app_env_valid": True,
            "postgres_ok": False,
            "redis_ok": True,
            "minio_ok": True,
            "model_loaded": True,
        },
        "reason": "postgres_not_ready: connection refused",
    }


def test_local_allows_missing_api_key_when_other_checks_ok(monkeypatch) -> None:
    _mock_all_infra_ok(monkeypatch)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "local")
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
            "postgres_ok": True,
            "redis_ok": True,
            "minio_ok": True,
            "model_loaded": True,
        },
    }


def test_not_ready_when_active_model_fails_to_load(monkeypatch, tmp_path) -> None:
    _mock_all_infra_ok(monkeypatch)
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
        "postgres_ok": True,
        "redis_ok": True,
        "minio_ok": True,
        "model_loaded": False,
    }
    assert isinstance(body.get("reason"), str)
    assert body["reason"].startswith("model_not_loaded")
