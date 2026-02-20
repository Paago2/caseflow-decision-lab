from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceChunk:
    case_id: str
    document_id: str
    chunk_id: str
    text: str
    start_char: int
    end_char: int
    source: str
    page: int | None = None


def chunk_text(
    *,
    case_id: str,
    document_id: str,
    text: str,
    source: str = "provenance",
    chunk_size: int = 700,
    overlap: int = 100,
) -> list[EvidenceChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    if not text:
        return []

    step = chunk_size - overlap
    chunks: list[EvidenceChunk] = []
    text_len = len(text)

    for start in range(0, text_len, step):
        end = min(start + chunk_size, text_len)
        chunk_text_value = text[start:end]
        chunk_key = f"{case_id}|{document_id}|{start}|{end}"
        chunk_id = hashlib.sha256(chunk_key.encode("utf-8")).hexdigest()[:16]
        chunks.append(
            EvidenceChunk(
                case_id=case_id,
                document_id=document_id,
                chunk_id=chunk_id,
                text=chunk_text_value,
                start_char=start,
                end_char=end,
                source=source,
                page=None,
            )
        )
        if end >= text_len:
            break

    return chunks
