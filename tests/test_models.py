import json

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache
from caseflow.ml.registry import clear_active_model


def _write_model_file(
    registry_dir, model_id: str, *, bias: float, weights: list[float]
) -> None:
    model_dir = registry_dir / model_id
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.json").write_text(
        json.dumps(
            {
                "model_id": model_id,
                "type": "linear",
                "bias": bias,
                "weights": weights,
            }
        ),
        encoding="utf-8",
    )


def _configure_tmp_registry(monkeypatch, tmp_path) -> None:
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    _write_model_file(registry_dir, "baseline_v1", bias=0.2, weights=[0.5, -0.1, 0.05])
    _write_model_file(registry_dir, "baseline_v2", bias=-0.1, weights=[0.25, 0.4, -0.2])

    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("MODEL_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v1")
    clear_settings_cache()
    clear_active_model()


def test_get_models_returns_active_and_sorted_available_ids(
    monkeypatch, tmp_path
) -> None:
    _configure_tmp_registry(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.get("/models", headers={"X-API-Key": "server-key"})

    assert response.status_code == 200
    assert response.json() == {
        "active_model_id": "baseline_v1",
        "available_model_ids": ["baseline_v1", "baseline_v2"],
    }


def test_activate_model_switches_active_model(monkeypatch, tmp_path) -> None:
    _configure_tmp_registry(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.post(
            "/models/activate/baseline_v2",
            headers={"X-API-Key": "server-key"},
        )

    assert response.status_code == 200
    assert response.json() == {"active_model_id": "baseline_v2"}


def test_predict_reflects_activated_model(monkeypatch, tmp_path) -> None:
    _configure_tmp_registry(monkeypatch, tmp_path)
    payload = {"features": [1.0, 2.0, 3.0]}

    with TestClient(app) as client:
        before = client.post("/predict", json=payload)
        activate = client.post(
            "/models/activate/baseline_v2",
            headers={"X-API-Key": "server-key"},
        )
        after = client.post("/predict", json=payload)

    assert before.status_code == 200
    assert activate.status_code == 200
    assert after.status_code == 200

    before_body = before.json()
    after_body = after.json()
    assert before_body["model_id"] == "baseline_v1"
    assert after_body["model_id"] == "baseline_v2"
    assert before_body["score"] != after_body["score"]


def test_models_endpoints_require_api_key(monkeypatch, tmp_path) -> None:
    _configure_tmp_registry(monkeypatch, tmp_path)

    with TestClient(app) as client:
        missing_models = client.get("/models")
        wrong_models = client.get("/models", headers={"X-API-Key": "wrong"})
        missing_activate = client.post("/models/activate/baseline_v2")
        wrong_activate = client.post(
            "/models/activate/baseline_v2",
            headers={"X-API-Key": "wrong"},
        )

    for response in [missing_models, wrong_models, missing_activate, wrong_activate]:
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
