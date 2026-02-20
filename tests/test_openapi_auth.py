from fastapi.testclient import TestClient

from caseflow.api.app import app


def test_openapi_includes_x_api_key_security_scheme() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert openapi["components"]["securitySchemes"]["ApiKeyAuth"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }


def test_protected_ping_has_security_requirement_in_openapi() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert openapi["paths"]["/protected/ping"]["get"]["security"] == [
        {"ApiKeyAuth": []}
    ]


def test_health_has_no_security_requirement_in_openapi() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert "security" not in openapi["paths"]["/health"]["get"]


def test_decision_has_no_security_requirement_in_openapi() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert "security" not in openapi["paths"]["/decision"]["post"]


def test_metrics_has_no_security_requirement_in_openapi() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert "security" not in openapi["paths"]["/metrics"]["get"]


def test_mortgage_decision_has_no_security_requirement_in_openapi() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert "security" not in openapi["paths"]["/mortgage/decision"]["post"]


def test_underwriter_run_has_no_security_requirement_in_openapi() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert "security" not in openapi["paths"]["/underwriter/run"]["post"]


def test_documents_endpoints_have_no_security_requirement_in_openapi() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert "security" not in openapi["paths"]["/documents/intake"]["post"]
    assert "security" not in openapi["paths"]["/documents/decision"]["post"]


def test_ocr_extract_has_no_security_requirement_in_openapi() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert "security" not in openapi["paths"]["/ocr/extract"]["post"]


def test_models_endpoints_have_security_requirement_in_openapi() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()

    assert openapi["paths"]["/models"]["get"]["security"] == [{"ApiKeyAuth": []}]
    assert openapi["paths"]["/models/activate/{model_id}"]["post"]["security"] == [
        {"ApiKeyAuth": []}
    ]
