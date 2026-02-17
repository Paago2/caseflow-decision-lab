import json
import logging

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.logging import JsonFormatter


def test_request_log_is_json_and_contains_request_id(caplog) -> None:
    caplog.set_level(logging.INFO)
    caplog.handler.setFormatter(JsonFormatter())

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200

    parsed_records: list[dict[str, object]] = []
    for line in caplog.text.splitlines():
        try:
            parsed_records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    assert parsed_records
    assert any(record.get("message") for record in parsed_records)
    assert any("request_id" in record for record in parsed_records)
