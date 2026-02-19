import json
import logging

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.logging import JsonFormatter
from caseflow.core.settings import clear_settings_cache
from caseflow.ml.registry import clear_active_model


def _configure_tmp_registry_with_decision_models(monkeypatch, tmp_path) -> None:
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    models = {
        "decision_approve": 220.0,
        "decision_decline": 100.0,
        "decision_review": 150.0,
    }

    for model_id, bias in models.items():
        model_dir = registry_dir / model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "model.json").write_text(
            json.dumps(
                {
                    "model_id": model_id,
                    "type": "linear",
                    "bias": bias,
                    "weights": [0.0, 0.0, 0.0],
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("API_KEY", "server-key")
    monkeypatch.setenv("MODEL_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setenv("ACTIVE_MODEL_ID", "decision_review")
    clear_settings_cache()
    clear_active_model()


def test_decision_outputs_for_all_policy_bands(monkeypatch, tmp_path) -> None:
    _configure_tmp_registry_with_decision_models(monkeypatch, tmp_path)

    with TestClient(app) as client:
        activate_approve = client.post(
            "/models/activate/decision_approve",
            headers={"X-API-Key": "server-key"},
        )
        approve = client.post("/decision", json={"features": [1.0, 2.0, 3.0]})

        activate_decline = client.post(
            "/models/activate/decision_decline",
            headers={"X-API-Key": "server-key"},
        )
        decline = client.post("/decision", json={"features": [1.0, 2.0, 3.0]})

        activate_review = client.post(
            "/models/activate/decision_review",
            headers={"X-API-Key": "server-key"},
        )
        review = client.post("/decision", json={"features": [1.0, 2.0, 3.0]})

    assert activate_approve.status_code == 200
    assert approve.status_code == 200
    assert approve.json()["decision"] == "approve"
    assert approve.json()["reasons"] == ["score_above_approve_threshold"]

    assert activate_decline.status_code == 200
    assert decline.status_code == 200
    assert decline.json()["decision"] == "decline"
    assert decline.json()["reasons"] == ["score_below_decline_threshold"]

    assert activate_review.status_code == 200
    assert review.status_code == 200
    assert review.json()["decision"] == "review"
    assert review.json()["reasons"] == ["score_in_review_band"]


def test_decision_dict_input_works_with_schema_model(monkeypatch) -> None:
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
            "/decision",
            json={
                "features": {
                    "age": 0.1,
                    "sex": -1.2,
                    "bmi": 2.3,
                    "bp": 0.0,
                }
            },
            headers={"X-Request-Id": "decision-dict-req"},
        )

    assert activate.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "diabetes_schema_v2"
    assert isinstance(body["score"], float)
    assert body["decision"] in {"approve", "decline", "review"}
    assert body["reasons"]
    assert body["request_id"] == "decision-dict-req"
    assert response.headers["X-Request-Id"] == "decision-dict-req"


def test_decision_legacy_list_input_works() -> None:
    response = TestClient(app).post(
        "/decision",
        json={"features": [0.1, -1.2, 2.3]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model_id"]
    assert isinstance(body["score"], float)
    assert body["decision"] in {"approve", "decline", "review"}
    assert isinstance(body["reasons"], list)
    assert body["request_id"] == response.headers["X-Request-Id"]


def test_decision_emits_structured_log(caplog) -> None:
    caplog.set_level(logging.INFO)
    caplog.handler.setFormatter(JsonFormatter())

    client = TestClient(app)
    response = client.post("/decision", json={"features": [0.1, -1.2, 2.3]})

    assert response.status_code == 200

    parsed_records: list[dict[str, object]] = []
    for line in caplog.text.splitlines():
        try:
            parsed_records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    decision_records = [
        record for record in parsed_records if record.get("event") == "decision_made"
    ]
    assert decision_records

    record = decision_records[-1]
    assert record["decision"] in {"approve", "decline", "review"}
    assert isinstance(record["score"], float)
    assert isinstance(record["model_id"], str)
    assert isinstance(record["request_id"], str)
