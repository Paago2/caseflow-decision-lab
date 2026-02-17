from fastapi.testclient import TestClient

from caseflow.api.app import app


def test_request_id_header_is_propagated_when_provided() -> None:
    client = TestClient(app)

    response = client.get("/health", headers={"X-Request-Id": "abc"})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "abc"


def test_request_id_header_is_generated_when_missing() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    generated_request_id = response.headers.get("X-Request-Id")

    assert generated_request_id is not None
    assert generated_request_id.strip() != ""
    assert len(generated_request_id) >= 16
