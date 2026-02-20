from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from caseflow.domain.mortgage.evidence import chunk_text
from caseflow.domain.mortgage.provenance import load_extracted_text
from caseflow.ml.vector_store import FileVectorStore

router = APIRouter()
logger = logging.getLogger(__name__)


class EvidenceDocumentRef(BaseModel):
    document_id: str


class EvidenceIndexRequest(BaseModel):
    documents: list[EvidenceDocumentRef]
    overwrite: bool = False


@router.post("/mortgage/{case_id}/evidence/index")
async def mortgage_evidence_index_endpoint(
    case_id: str,
    payload: EvidenceIndexRequest,
    request: Request,
) -> dict[str, object]:
    normalized_case_id = case_id.strip()
    if not normalized_case_id:
        raise HTTPException(status_code=422, detail="'case_id' must be non-empty")

    if not payload.documents:
        raise HTTPException(
            status_code=422,
            detail="'documents' must be a non-empty list",
        )

    all_chunks = []
    for item in payload.documents:
        document_id = item.document_id.strip()
        if not document_id:
            raise HTTPException(
                status_code=422,
                detail="'document_id' must be non-empty",
            )

        try:
            extracted = load_extracted_text(normalized_case_id, document_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        all_chunks.extend(
            chunk_text(
                case_id=normalized_case_id,
                document_id=document_id,
                text=extracted,
                source="provenance",
            )
        )

    store = FileVectorStore()
    if payload.overwrite:
        indexed_chunks = store.overwrite_case(normalized_case_id, all_chunks)
    else:
        indexed_chunks = store.add_documents(all_chunks)

    request_id = getattr(request.state, "request_id", "") or ""
    logger.info(
        "evidence_indexed",
        extra={
            "event": "evidence_indexed",
            "case_id": normalized_case_id,
            "indexed_chunks": indexed_chunks,
            "doc_count": len(payload.documents),
            "request_id": request_id,
        },
    )

    return {
        "case_id": normalized_case_id,
        "indexed_chunks": indexed_chunks,
        "request_id": request_id,
    }


@router.get("/mortgage/{case_id}/evidence/search")
async def mortgage_evidence_search_endpoint(
    case_id: str,
    request: Request,
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=50),
) -> dict[str, object]:
    normalized_case_id = case_id.strip()
    if not normalized_case_id:
        raise HTTPException(status_code=422, detail="'case_id' must be non-empty")

    store = FileVectorStore()
    try:
        matches = store.search(q, top_k=top_k, case_id=normalized_case_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    request_id = getattr(request.state, "request_id", "") or ""
    logger.info(
        "evidence_searched",
        extra={
            "event": "evidence_searched",
            "case_id": normalized_case_id,
            "top_k": top_k,
            "request_id": request_id,
        },
    )

    return {
        "case_id": normalized_case_id,
        "query": q,
        "top_k": top_k,
        "results": [
            {
                "score": item.score,
                "document_id": item.chunk.document_id,
                "chunk_id": item.chunk.chunk_id,
                "start_char": item.chunk.start_char,
                "end_char": item.chunk.end_char,
                "text": item.chunk.text,
            }
            for item in matches
        ],
        "request_id": request_id,
    }
