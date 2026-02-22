from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from caseflow.api import routes_ingest
from caseflow.api.app import app
from caseflow.core.audit import clear_audit_sink_cache
from caseflow.core.metrics import clear_metrics
from caseflow.core.settings import clear_settings_cache


def _write_files(root: Path) -> None:
    (root / "a.txt").write_text("hello", encoding="utf-8")
    (root / "nested").mkdir(parents=True, exist_ok=True)
    (root / "nested" / "b.txt").write_text("world", encoding="utf-8")
    (root / "nested" / "c.txt").write_text("!", encoding="utf-8")


def _reset_runtime() -> None:
    clear_settings_cache()
    clear_audit_sink_cache()
    clear_metrics()


def test_ingest_raw_dry_run_records_completed_without_upload(
    monkeypatch, tmp_path: Path
) -> None:
    _write_files(tmp_path)
    _reset_runtime()

    calls: dict[str, object] = {}

    monkeypatch.setenv("AUDIT_SINK", "log")
    monkeypatch.setattr(
        routes_ingest.ingestion_repo,
        "create_run",
        lambda **kwargs: calls.setdefault("create_run", kwargs),
    )
    monkeypatch.setattr(
        routes_ingest.ingestion_repo,
        "complete_run",
        lambda **kwargs: calls.setdefault("complete_run", kwargs),
    )
    monkeypatch.setattr(
        routes_ingest.ingestion_repo,
        "fail_run",
        lambda **kwargs: calls.setdefault("fail_run", kwargs),
    )

    def _unexpected_upload(**_: object) -> None:
        raise AssertionError("upload should not be called in dry_run")

    monkeypatch.setattr(routes_ingest, "_upload_files", _unexpected_upload)

    response = TestClient(app).post(
        "/ingest/raw",
        json={"source_path": str(tmp_path), "dry_run": True, "limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["manifest"]["file_count"] == 2
    assert body["manifest"]["dry_run"] is True
    assert body["manifest"]["source_path"] == str(tmp_path.resolve())

    assert "create_run" in calls
    assert "complete_run" in calls
    assert "fail_run" not in calls


def test_ingest_raw_upload_path_calls_uploader(monkeypatch, tmp_path: Path) -> None:
    _write_files(tmp_path)
    _reset_runtime()

    calls: dict[str, object] = {}

    monkeypatch.setenv("AUDIT_SINK", "log")
    monkeypatch.setattr(
        routes_ingest.ingestion_repo,
        "create_run",
        lambda **kwargs: calls.setdefault("create_run", kwargs),
    )
    monkeypatch.setattr(
        routes_ingest.ingestion_repo,
        "complete_run",
        lambda **kwargs: calls.setdefault("complete_run", kwargs),
    )
    monkeypatch.setattr(
        routes_ingest.ingestion_repo,
        "fail_run",
        lambda **kwargs: calls.setdefault("fail_run", kwargs),
    )
    monkeypatch.setattr(
        routes_ingest,
        "_upload_files",
        lambda **kwargs: calls.setdefault("upload", kwargs),
    )

    response = TestClient(app).post(
        "/ingest/raw",
        json={"source_path": str(tmp_path), "dry_run": False, "limit": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["manifest"]["file_count"] == 1
    assert "upload" in calls
    assert "fail_run" not in calls


def test_ingest_raw_failed_upload_marks_failed(monkeypatch, tmp_path: Path) -> None:
    _write_files(tmp_path)
    _reset_runtime()

    calls: dict[str, object] = {}

    monkeypatch.setenv("AUDIT_SINK", "log")
    monkeypatch.setattr(
        routes_ingest.ingestion_repo,
        "create_run",
        lambda **kwargs: calls.setdefault("create_run", kwargs),
    )
    monkeypatch.setattr(
        routes_ingest.ingestion_repo,
        "complete_run",
        lambda **kwargs: calls.setdefault("complete_run", kwargs),
    )
    monkeypatch.setattr(
        routes_ingest.ingestion_repo,
        "fail_run",
        lambda **kwargs: calls.setdefault("fail_run", kwargs),
    )

    def _failing_upload(**_: object) -> None:
        raise RuntimeError("upload exploded")

    monkeypatch.setattr(routes_ingest, "_upload_files", _failing_upload)

    response = TestClient(app).post(
        "/ingest/raw",
        json={"source_path": str(tmp_path), "dry_run": False},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["status"] == "failed"
    assert "upload exploded" in body["reason"]
    assert "fail_run" in calls
    assert "complete_run" not in calls
