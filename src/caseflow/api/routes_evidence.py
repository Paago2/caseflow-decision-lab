from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from caseflow.core.metrics import increment_metric, observe_ms_metric, set_gauge_metric
from caseflow.core.settings import get_settings
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


class EvidenceReindexRequest(BaseModel):
    documents: list[EvidenceDocumentRef]


def _collect_chunks(
    *,
    case_id: str,
    documents: list[EvidenceDocumentRef],
) -> list:
    if not documents:
        raise HTTPException(
            status_code=422,
            detail="'documents' must be a non-empty list",
        )

    all_chunks = []
    for item in documents:
        document_id = item.document_id.strip()
        if not document_id:
            raise HTTPException(
                status_code=422,
                detail="'document_id' must be non-empty",
            )

        try:
            extracted = load_extracted_text(case_id, document_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        all_chunks.extend(
            chunk_text(
                case_id=case_id,
                document_id=document_id,
                text=extracted,
                source="provenance",
            )
        )

    return all_chunks


@router.post("/mortgage/{case_id}/evidence/index")
async def mortgage_evidence_index_endpoint(
    case_id: str,
    payload: EvidenceIndexRequest,
    request: Request,
) -> dict[str, object]:
    started = time.perf_counter()
    increment_metric("evidence_index_requests_total")

    normalized_case_id = case_id.strip()
    if not normalized_case_id:
        raise HTTPException(status_code=422, detail="'case_id' must be non-empty")

    all_chunks = _collect_chunks(
        case_id=normalized_case_id, documents=payload.documents
    )

    store = FileVectorStore()
    if payload.overwrite:
        indexed_chunks = store.overwrite_case(normalized_case_id, all_chunks)
    else:
        indexed_chunks = store.add_documents(all_chunks)
    increment_metric("evidence_index_chunks_total", float(indexed_chunks))
    observe_ms_metric(
        "evidence_index_latency_ms", (time.perf_counter() - started) * 1000
    )

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


@router.post("/mortgage/{case_id}/evidence/reindex")
async def mortgage_evidence_reindex_endpoint(
    case_id: str,
    payload: EvidenceReindexRequest,
    request: Request,
) -> dict[str, object]:
    normalized_case_id = case_id.strip()
    if not normalized_case_id:
        raise HTTPException(status_code=422, detail="'case_id' must be non-empty")

    chunks = _collect_chunks(case_id=normalized_case_id, documents=payload.documents)
    indexed_chunks = FileVectorStore().overwrite_case(normalized_case_id, chunks)
    increment_metric("evidence_index_requests_total")
    increment_metric("evidence_index_chunks_total", float(indexed_chunks))

    request_id = getattr(request.state, "request_id", "") or ""
    return {
        "case_id": normalized_case_id,
        "indexed_chunks": indexed_chunks,
        "request_id": request_id,
    }


@router.get("/mortgage/{case_id}/evidence/stats")
async def mortgage_evidence_stats_endpoint(
    case_id: str,
    request: Request,
) -> dict[str, object]:
    normalized_case_id = case_id.strip()
    if not normalized_case_id:
        raise HTTPException(status_code=422, detail="'case_id' must be non-empty")

    stats = FileVectorStore().case_stats(normalized_case_id)
    request_id = getattr(request.state, "request_id", "") or ""
    return {
        "case_id": normalized_case_id,
        "num_chunks": stats["num_chunks"],
        "documents": stats["documents"],
        "updated_at": stats["updated_at"],
        "request_id": request_id,
    }


@router.delete("/mortgage/{case_id}/evidence")
async def mortgage_evidence_delete_endpoint(
    case_id: str,
    request: Request,
) -> dict[str, object]:
    normalized_case_id = case_id.strip()
    if not normalized_case_id:
        raise HTTPException(status_code=422, detail="'case_id' must be non-empty")

    deleted_chunks = FileVectorStore().delete_case(normalized_case_id)
    request_id = getattr(request.state, "request_id", "") or ""
    return {
        "case_id": normalized_case_id,
        "deleted_chunks": deleted_chunks,
        "request_id": request_id,
    }


@router.get("/mortgage/{case_id}/evidence/search")
async def mortgage_evidence_search_endpoint(
    case_id: str,
    request: Request,
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=50),
) -> dict[str, object]:
    started = time.perf_counter()
    increment_metric("evidence_search_requests_total")

    normalized_case_id = case_id.strip()
    if not normalized_case_id:
        raise HTTPException(status_code=422, detail="'case_id' must be non-empty")

    store = FileVectorStore()
    min_score = get_settings().evidence_min_score
    try:
        matches = store.search(
            q,
            top_k=top_k,
            case_id=normalized_case_id,
            min_score=min_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    observe_ms_metric(
        "evidence_search_latency_ms", (time.perf_counter() - started) * 1000
    )
    top_score = matches[0].score if matches else 0.0
    set_gauge_metric("evidence_search_top_score", float(top_score))

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
        "min_score": min_score,
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
