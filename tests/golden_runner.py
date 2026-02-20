from __future__ import annotations

import base64
import difflib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from caseflow.api.app import app
from caseflow.core.settings import clear_settings_cache

REQUESTS_DIR = Path("tests/fixtures/golden/requests")
EXPECTED_DIR = Path("tests/fixtures/golden/expected")


def _normalize_underwrite_response(payload: dict[str, object]) -> dict[str, object]:
    normalized = json.loads(json.dumps(payload))
    normalized.pop("request_id", None)

    risk_score = normalized.get("risk_score")
    if isinstance(risk_score, (float, int)):
        normalized["risk_score"] = round(float(risk_score), 6)

    policy = normalized.get("policy")
    if isinstance(policy, dict):
        derived = policy.get("derived")
        if isinstance(derived, dict):
            policy["derived"] = {
                str(key): round(float(value), 6)
                for key, value in derived.items()
                if isinstance(value, (float, int))
            }

    justification = normalized.get("justification")
    if isinstance(justification, dict):
        citations = justification.get("citations", [])
        if isinstance(citations, list):
            cleaned: list[dict[str, object]] = []
            for item in citations:
                if not isinstance(item, dict):
                    continue
                score = item.get("score")
                cleaned.append(
                    {
                        "document_id": str(item.get("document_id", "")),
                        "chunk_id": str(item.get("chunk_id", "")),
                        "start_char": int(item.get("start_char", 0)),
                        "end_char": int(item.get("end_char", 0)),
                        "score": (
                            round(float(score), 6)
                            if isinstance(score, (float, int))
                            else 0.0
                        ),
                    }
                )
            justification["citations"] = sorted(
                cleaned,
                key=lambda row: (row["chunk_id"], row["document_id"]),
            )

    return normalized


def _run_single_fixture(path: Path, update: bool) -> tuple[bool, str]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    case_id = str(fixture["case_id"])

    runtime_root = Path("artifacts") / "golden_runtime" / path.stem
    provenance_dir = runtime_root / "provenance"
    evidence_dir = runtime_root / "evidence"

    import os

    os.environ["PROVENANCE_DIR"] = str(provenance_dir)
    os.environ["EVIDENCE_INDEX_DIR"] = str(evidence_dir)
    os.environ["EVIDENCE_MIN_SCORE"] = "0.0"
    os.environ["UNDERWRITE_ENGINE"] = str(fixture.get("underwrite_engine", "graph"))
    os.environ["JUSTIFIER_PROVIDER"] = str(
        fixture.get("justifier_provider", "deterministic")
    )
    clear_settings_cache()

    client = TestClient(app)

    docs = fixture.get("evidence_documents", [])
    if isinstance(docs, list) and docs:
        document_ids: list[str] = []
        for idx, doc in enumerate(docs):
            if not isinstance(doc, dict):
                continue
            text = str(doc.get("text", ""))
            filename = str(doc.get("filename", f"doc_{idx}.txt"))
            ocr = client.post(
                "/ocr/extract",
                json={
                    "case_id": case_id,
                    "document": {
                        "filename": filename,
                        "content_type": "text/plain",
                        "content_b64": base64.b64encode(text.encode("utf-8")).decode(
                            "ascii"
                        ),
                    },
                },
            )
            if ocr.status_code != 200:
                return False, f"OCR failed for {path.name}: {ocr.text}"
            document_ids.append(str(ocr.json()["document_id"]))

        reindex = client.post(
            f"/mortgage/{case_id}/evidence/reindex",
            json={"documents": [{"document_id": doc_id} for doc_id in document_ids]},
        )
        if reindex.status_code != 200:
            return False, f"Reindex failed for {path.name}: {reindex.text}"

    underwrite_body = fixture["underwrite_request"]
    response = client.post(f"/mortgage/{case_id}/underwrite", json=underwrite_body)
    if response.status_code != 200:
        return False, f"Underwrite failed for {path.name}: {response.text}"

    normalized = _normalize_underwrite_response(response.json())
    expected_path = EXPECTED_DIR / path.name

    if update:
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.write_text(
            json.dumps(normalized, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return True, f"updated {expected_path}"

    if not expected_path.is_file():
        return (
            False,
            f"Missing expected golden file: {expected_path}. "
            "Run golden update to create it.",
        )

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    if expected != normalized:
        expected_text = json.dumps(expected, indent=2, sort_keys=True)
        actual_text = json.dumps(normalized, indent=2, sort_keys=True)
        diff = "\n".join(
            difflib.unified_diff(
                expected_text.splitlines(),
                actual_text.splitlines(),
                fromfile=str(expected_path),
                tofile=f"actual:{path.name}",
                lineterm="",
            )
        )
        return False, f"Golden mismatch for {path.name}:\n{diff}"

    return True, f"ok {path.name}"


def run_golden(update: bool = False) -> list[str]:
    request_files = sorted(REQUESTS_DIR.glob("*.json"))
    if not request_files:
        raise AssertionError(f"No golden request fixtures found under {REQUESTS_DIR}")

    messages: list[str] = []
    failures: list[str] = []
    for path in request_files:
        ok, message = _run_single_fixture(path, update=update)
        messages.append(message)
        if not ok:
            failures.append(message)

    if failures:
        details = "\n\n".join(failures)
        raise AssertionError(f"Golden underwrite regression failures:\n{details}")
    return messages
