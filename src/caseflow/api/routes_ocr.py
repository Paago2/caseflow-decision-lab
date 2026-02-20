from __future__ import annotations

import base64
import hashlib
import logging
from binascii import Error as BinasciiError
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from caseflow.domain.mortgage.ocr import extract_text
from caseflow.domain.mortgage.provenance import write_provenance_event

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ocr/extract")
async def ocr_extract_endpoint(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON object",
        )

    case_id = payload.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise HTTPException(
            status_code=422,
            detail="'case_id' must be a non-empty string",
        )

    document = payload.get("document")
    if not isinstance(document, dict):
        raise HTTPException(status_code=422, detail="'document' must be an object")

    filename = document.get("filename")
    if not isinstance(filename, str) or not filename.strip():
        raise HTTPException(
            status_code=422,
            detail="'document.filename' must be a non-empty string",
        )

    content_type = document.get("content_type")
    if not isinstance(content_type, str) or not content_type.strip():
        raise HTTPException(
            status_code=422,
            detail="'document.content_type' must be a non-empty string",
        )

    content_b64 = document.get("content_b64")
    if not isinstance(content_b64, str) or not content_b64.strip():
        raise HTTPException(
            status_code=422,
            detail="'document.content_b64' must be a non-empty base64 string",
        )

    try:
        content_bytes = base64.b64decode(content_b64, validate=True)
    except (BinasciiError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="'document.content_b64' must be valid base64",
        ) from exc

    try:
        extracted_text, extraction_meta = extract_text(content_bytes, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    document_id = hashlib.sha256(content_bytes).hexdigest()[:16]
    provenance = write_provenance_event(
        case_id=case_id.strip(),
        document_id=document_id,
        filename=filename.strip(),
        content_type=content_type.strip(),
        document_bytes=content_bytes,
        extracted_text=extracted_text,
        extraction_meta=extraction_meta,
    )

    request_id = getattr(request.state, "request_id", "") or ""
    logger.info(
        "ocr_extracted",
        extra={
            "event": "ocr_extracted",
            "case_id": case_id.strip(),
            "document_id": document_id,
            "method": extraction_meta.get("method"),
            "engine": extraction_meta.get("engine"),
            "char_count": extraction_meta.get("char_count"),
            "request_id": request_id,
        },
    )

    return {
        "case_id": case_id.strip(),
        "document_id": document_id,
        "content_type": content_type.strip(),
        "filename": filename.strip(),
        "extraction_meta": extraction_meta,
        "provenance_path": provenance["provenance_path"],
        "text_path": provenance["text_path"],
        "request_id": request_id,
    }
