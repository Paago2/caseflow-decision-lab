from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from caseflow.core.settings import get_settings


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_provenance_event(
    *,
    case_id: str,
    document_id: str,
    filename: str,
    content_type: str,
    document_bytes: bytes,
    extracted_text: str,
    extraction_meta: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    base_dir = Path(settings.provenance_dir)
    case_dir = base_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    text_path = case_dir / f"{document_id}.txt"
    provenance_path = case_dir / f"{document_id}.json"

    text_path.write_text(extracted_text, encoding="utf-8")

    now = _iso_utc_now()
    provenance_event: dict[str, Any] = {
        "case_id": case_id,
        "document_id": document_id,
        "filename": filename,
        "content_type": content_type,
        "sha256": hashlib.sha256(document_bytes).hexdigest(),
        "extraction_meta": extraction_meta,
        "text_path": str(text_path),
        "created_at": now,
        "updated_at": now,
    }

    provenance_path.write_text(
        json.dumps(provenance_event, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )

    return {
        "provenance_path": str(provenance_path),
        "text_path": str(text_path),
        "provenance": provenance_event,
    }


def load_provenance_event(case_id: str, document_id: str) -> dict[str, Any]:
    settings = get_settings()
    provenance_path = Path(settings.provenance_dir) / case_id / f"{document_id}.json"
    if not provenance_path.is_file():
        raise FileNotFoundError(
            f"Provenance event not found for case_id={case_id}, "
            f"document_id={document_id}"
        )

    try:
        payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Provenance JSON is invalid for case_id={case_id}, "
            f"document_id={document_id}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            f"Provenance JSON must be an object for case_id={case_id}, "
            f"document_id={document_id}"
        )

    return payload


def load_extracted_text(case_id: str, document_id: str) -> str:
    payload = load_provenance_event(case_id, document_id)
    text_path = payload.get("text_path")
    if isinstance(text_path, str) and text_path.strip():
        candidate = Path(text_path)
    else:
        settings = get_settings()
        candidate = Path(settings.provenance_dir) / case_id / f"{document_id}.txt"

    if not candidate.is_file():
        raise FileNotFoundError(
            f"Extracted text not found for case_id={case_id}, document_id={document_id}"
        )

    return candidate.read_text(encoding="utf-8")
