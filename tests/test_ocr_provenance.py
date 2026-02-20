import base64
import hashlib
import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.logging import JsonFormatter
from caseflow.core.settings import clear_settings_cache


def test_ocr_extract_text_plain_writes_provenance_and_logs(
    monkeypatch, tmp_path, caplog
) -> None:
    monkeypatch.setenv("PROVENANCE_DIR", str(tmp_path))
    monkeypatch.setenv("OCR_ENGINE", "noop")
    clear_settings_cache()

    caplog.set_level(logging.INFO)
    caplog.handler.setFormatter(JsonFormatter())

    content_bytes = b"Hello mortgage OCR"
    payload = {
        "case_id": "case_ocr_001",
        "document": {
            "filename": "note.txt",
            "content_type": "text/plain",
            "content_b64": base64.b64encode(content_bytes).decode("ascii"),
        },
    }

    response = TestClient(app).post("/ocr/extract", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "case_ocr_001"

    expected_document_id = hashlib.sha256(content_bytes).hexdigest()[:16]
    assert body["document_id"] == expected_document_id
    assert body["extraction_meta"] == {
        "method": "plain_text",
        "engine": "builtin",
        "char_count": len(content_bytes.decode("utf-8")),
    }

    provenance_path = Path(body["provenance_path"])
    text_path = Path(body["text_path"])
    assert provenance_path.exists()
    assert text_path.exists()
    assert str(provenance_path).startswith(str(tmp_path))
    assert str(text_path).startswith(str(tmp_path))

    saved_text = text_path.read_text(encoding="utf-8")
    assert saved_text == "Hello mortgage OCR"

    provenance_payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance_payload["case_id"] == "case_ocr_001"
    assert provenance_payload["document_id"] == expected_document_id
    assert provenance_payload["filename"] == "note.txt"
    assert provenance_payload["content_type"] == "text/plain"
    assert provenance_payload["sha256"] == hashlib.sha256(content_bytes).hexdigest()
    assert provenance_payload["text_path"] == str(text_path)
    assert provenance_payload["extraction_meta"] == body["extraction_meta"]
    assert provenance_payload["created_at"]
    assert provenance_payload["updated_at"]

    parsed_records: list[dict[str, object]] = []
    for line in caplog.text.splitlines():
        try:
            parsed_records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    assert any(record.get("event") == "ocr_extracted" for record in parsed_records)


def test_ocr_extract_invalid_base64_uses_standard_error_envelope() -> None:
    payload = {
        "case_id": "case_ocr_002",
        "document": {
            "filename": "broken.txt",
            "content_type": "text/plain",
            "content_b64": "not base64!!",
        },
    }

    response = TestClient(app).post("/ocr/extract", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert body["error"]["status"] == 422
    assert "valid base64" in body["error"]["message"]
    assert body["error"]["request_id"] == response.headers["X-Request-Id"]


def test_ocr_extract_unsupported_content_type_uses_standard_error_envelope() -> None:
    payload = {
        "case_id": "case_ocr_003",
        "document": {
            "filename": "data.bin",
            "content_type": "application/octet-stream",
            "content_b64": base64.b64encode(b"abc").decode("ascii"),
        },
    }

    response = TestClient(app).post("/ocr/extract", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert body["error"]["status"] == 422
    assert "Unsupported content_type" in body["error"]["message"]
    assert body["error"]["request_id"] == response.headers["X-Request-Id"]
