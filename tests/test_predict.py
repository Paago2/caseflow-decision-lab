from fastapi.testclient import TestClient

from caseflow.api.app import app


def test_predict_valid_input_returns_prediction_and_request_id() -> None:
    client = TestClient(app)

    response = client.post(
        "/predict",
        json={"features": [0.1, -1.2, 2.3, 0.4]},
        headers={"X-Request-Id": "req-123"},
    )

    assert response.status_code == 200
    body = response.json()

    assert "prediction" in body
    assert isinstance(body["prediction"], float)
    assert 0.0 <= body["prediction"] <= 1.0
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
