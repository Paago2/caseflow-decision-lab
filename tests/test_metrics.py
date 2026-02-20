from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.metrics import clear_metrics


def test_metrics_endpoint_returns_prometheus_text() -> None:
    clear_metrics()
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    content_type = response.headers["content-type"]
    assert "text/plain" in content_type
    assert "version=0.0.4" in content_type


def test_metrics_include_request_counter_after_health_request() -> None:
    clear_metrics()
    client = TestClient(app)

    health = client.get("/health")
    metrics = client.get("/metrics")

    assert health.status_code == 200
    assert metrics.status_code == 200
    body = metrics.text
    assert "http_requests_total" in body
    assert 'method="GET",path="/health",status="200"' in body
