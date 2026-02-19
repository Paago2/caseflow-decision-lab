from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache
from caseflow.ml.registry import clear_active_model


def test_predict_valid_input_returns_prediction_and_request_id() -> None:
    client = TestClient(app)

    response = client.post(
        "/predict",
        json={"features": [0.1, -1.2, 2.3]},
        headers={"X-Request-Id": "req-123"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["model_id"] == "baseline_v1"
    assert "score" in body
    assert isinstance(body["score"], float)
    assert body["request_id"] == "req-123"
    assert response.headers["X-Request-Id"] == "req-123"


def test_predict_invalid_input_returns_standardized_error_envelope() -> None:
    client = TestClient(app)

    response = client.post("/predict", json={"features": [1.0, 2.0]})

    assert response.status_code == 400
    body = response.json()

    assert "error" in body
    assert body["error"]["code"] == "http_error"
    assert body["error"]["status"] == 400
    assert body["error"]["request_id"] == response.headers["X-Request-Id"]


def test_predict_named_features_succeeds_with_schema_model(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v1")
    clear_settings_cache()
    clear_active_model()

    payload = {
        "features": {
            "age": 0.1,
            "sex": -1.2,
            "bmi": 2.3,
            "bp": 0.0,
            "s1": 0.5,
            "s2": -0.2,
            "s3": 0.1,
            "s4": 0.3,
            "s5": -0.4,
            "s6": 0.2,
        }
    }

    with TestClient(app) as client:
        activate = client.post(
            "/models/activate/diabetes_schema_v1",
            headers={"X-API-Key": "server-key"},
        )
        response = client.post("/predict", json=payload)

    assert activate.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "diabetes_schema_v1"
    assert isinstance(body["score"], float)


def test_predict_legacy_list_still_works_with_schema_model(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v1")
    clear_settings_cache()
    clear_active_model()

    with TestClient(app) as client:
        activate = client.post(
            "/models/activate/diabetes_schema_v1",
            headers={"X-API-Key": "server-key"},
        )
        response = client.post(
            "/predict",
            json={"features": [0.1, -1.2, 2.3, 0.0, 0.5, -0.2, 0.1, 0.3, -0.4, 0.2]},
        )

    assert activate.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "diabetes_schema_v1"
    assert isinstance(body["score"], float)


def test_predict_named_features_fails_without_schema_model(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v1")
    clear_settings_cache()
    clear_active_model()

    response = TestClient(app).post(
        "/predict",
        json={
            "features": {
                "age": 0.1,
                "sex": -1.2,
                "bmi": 2.3,
            }
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert body["error"]["status"] == 422
    assert body["error"]["message"] == (
        "'features' object is not supported for model without schema"
    )


def test_predict_named_features_missing_or_extra_key_returns_422(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v1")
    clear_settings_cache()
    clear_active_model()

    with TestClient(app) as client:
        activate = client.post(
            "/models/activate/diabetes_schema_v1",
            headers={"X-API-Key": "server-key"},
        )

        missing = client.post(
            "/predict",
            json={
                "features": {
                    "age": 0.1,
                    "sex": -1.2,
                    "bmi": 2.3,
                    "bp": 0.0,
                    "s1": 0.5,
                    "s2": -0.2,
                    "s3": 0.1,
                    "s4": 0.3,
                    "s5": -0.4,
                    # missing s6
                }
            },
        )

        extra = client.post(
            "/predict",
            json={
                "features": {
                    "age": 0.1,
                    "sex": -1.2,
                    "bmi": 2.3,
                    "bp": 0.0,
                    "s1": 0.5,
                    "s2": -0.2,
                    "s3": 0.1,
                    "s4": 0.3,
                    "s5": -0.4,
                    "s6": 0.2,
                    "unknown": 1.0,
                }
            },
        )

    assert activate.status_code == 200

    assert missing.status_code == 422
    missing_body = missing.json()
    assert missing_body["error"]["code"] == "http_error"
    assert missing_body["error"]["status"] == 422
    assert missing_body["error"]["message"] == "Missing required feature keys: s6"

    assert extra.status_code == 422
    extra_body = extra.json()
    assert extra_body["error"]["code"] == "http_error"
    assert extra_body["error"]["status"] == 422
    assert extra_body["error"]["message"] == "Unknown feature keys: unknown"


def test_predict_named_features_schema_v2_allows_missing_optional_with_defaults(
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v1")
    clear_settings_cache()
    clear_active_model()

    with TestClient(app) as client:
        activate = client.post(
            "/models/activate/diabetes_schema_v2",
            headers={"X-API-Key": "server-key"},
        )
        response = client.post(
            "/predict",
            json={
                "features": {
                    "age": 0.1,
                    "sex": -1.2,
                    "bmi": 2.3,
                    "bp": 0.0,
                    # optional s1..s6 omitted; defaults should be used
                }
            },
        )

    assert activate.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "diabetes_schema_v2"
    assert isinstance(body["score"], float)


def test_predict_named_features_schema_v2_missing_required_returns_422(
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v1")
    clear_settings_cache()
    clear_active_model()

    with TestClient(app) as client:
        activate = client.post(
            "/models/activate/diabetes_schema_v2",
            headers={"X-API-Key": "server-key"},
        )
        response = client.post(
            "/predict",
            json={
                "features": {
                    # missing required age
                    "sex": -1.2,
                    "bmi": 2.3,
                    "bp": 0.0,
                }
            },
        )

    assert activate.status_code == 200
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert body["error"]["status"] == 422
    assert body["error"]["message"] == "Missing required feature keys: age"


def test_predict_named_features_schema_v2_unknown_key_returns_422(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v1")
    clear_settings_cache()
    clear_active_model()

    with TestClient(app) as client:
        activate = client.post(
            "/models/activate/diabetes_schema_v2",
            headers={"X-API-Key": "server-key"},
        )
        response = client.post(
            "/predict",
            json={
                "features": {
                    "age": 0.1,
                    "sex": -1.2,
                    "bmi": 2.3,
                    "bp": 0.0,
                    "unknown": 1.0,
                }
            },
        )

    assert activate.status_code == 200
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert body["error"]["status"] == 422
    assert body["error"]["message"] == "Unknown feature keys: unknown"


def test_predict_legacy_list_still_works_with_schema_v2_model(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("ACTIVE_MODEL_ID", "baseline_v1")
    clear_settings_cache()
    clear_active_model()

    with TestClient(app) as client:
        activate = client.post(
            "/models/activate/diabetes_schema_v2",
            headers={"X-API-Key": "server-key"},
        )
        response = client.post(
            "/predict",
            json={"features": [0.1, -1.2, 2.3, 0.0, 0.5, -0.2, 0.1, 0.3, -0.4, 0.2]},
        )

    assert activate.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "diabetes_schema_v2"
    assert isinstance(body["score"], float)
