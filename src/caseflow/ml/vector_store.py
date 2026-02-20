from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from caseflow.core.settings import get_settings
from caseflow.domain.mortgage.evidence import EvidenceChunk
from caseflow.ml.embeddings import cosine_similarity, embed_text


@dataclass(frozen=True)
class SearchResult:
    chunk: EvidenceChunk
    score: float


class FileVectorStore:
    _CACHE: dict[str, tuple[float | None, list[dict[str, Any]]]] = {}

    def __init__(self, index_file: Path | None = None, dims: int = 128):
        if dims <= 0:
            raise ValueError("dims must be > 0")

        self._dims = dims
        if index_file is None:
            settings = get_settings()
            index_root = Path(settings.evidence_index_dir)
            self._index_file = index_root / "index.json"
        else:
            self._index_file = index_file

        self._index_file.parent.mkdir(parents=True, exist_ok=True)

    def _cache_key(self) -> str:
        return str(self._index_file.resolve())

    def _index_mtime(self) -> float | None:
        if not self._index_file.is_file():
            return None
        return self._index_file.stat().st_mtime

    def _load_records(self) -> list[dict[str, Any]]:
        cache_key = self._cache_key()
        mtime = self._index_mtime()
        cached = self._CACHE.get(cache_key)
        if cached is not None and cached[0] == mtime:
            return [dict(item) for item in cached[1]]

        if mtime is None:
            records: list[dict[str, Any]] = []
            self._CACHE[cache_key] = (None, records)
            return []

        try:
            payload = json.loads(self._index_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid evidence index JSON at {self._index_file}"
            ) from exc

        if not isinstance(payload, list):
            raise ValueError("Evidence index payload must be a JSON list")

        validated: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                validated.append(item)
        self._CACHE[cache_key] = (mtime, [dict(item) for item in validated])
        return validated

    def _write_records(self, records: list[dict[str, Any]]) -> None:
        self._index_file.write_text(
            json.dumps(records, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
        self._CACHE[self._cache_key()] = (
            self._index_mtime(),
            [dict(item) for item in records],
        )

    def _record_from_chunk(self, chunk: EvidenceChunk) -> dict[str, Any]:
        return {
            "case_id": chunk.case_id,
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "source": chunk.source,
            "page": chunk.page,
            "embedding": embed_text(chunk.text, dims=self._dims),
        }

    def add_documents(self, chunks: list[EvidenceChunk]) -> int:
        if not chunks:
            return 0

        records = self._load_records()
        by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
        for record in records:
            key = (
                str(record.get("case_id", "")),
                str(record.get("document_id", "")),
                str(record.get("chunk_id", "")),
            )
            by_key[key] = record

        for chunk in chunks:
            key = (chunk.case_id, chunk.document_id, chunk.chunk_id)
            by_key[key] = self._record_from_chunk(chunk)

        updated_records = sorted(
            by_key.values(),
            key=lambda r: (
                str(r.get("case_id", "")),
                str(r.get("document_id", "")),
                str(r.get("chunk_id", "")),
            ),
        )
        self._write_records(updated_records)
        return len(chunks)

    def overwrite_case(self, case_id: str, chunks: list[EvidenceChunk]) -> int:
        records = self._load_records()
        preserved = [record for record in records if record.get("case_id") != case_id]
        incoming = [self._record_from_chunk(chunk) for chunk in chunks]
        merged = sorted(
            [*preserved, *incoming],
            key=lambda r: (
                str(r.get("case_id", "")),
                str(r.get("document_id", "")),
                str(r.get("chunk_id", "")),
            ),
        )
        self._write_records(merged)
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 5,
        case_id: str | None = None,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be > 0")

        query_vector = embed_text(query, dims=self._dims)
        records = self._load_records()
        results: list[SearchResult] = []

        for record in records:
            record_case_id = str(record.get("case_id", ""))
            if case_id is not None and record_case_id != case_id:
                continue

            embedding = record.get("embedding")
            if not isinstance(embedding, list):
                continue

            try:
                vector = [float(value) for value in embedding]
            except (TypeError, ValueError):
                continue

            if len(vector) != self._dims:
                continue

            chunk = EvidenceChunk(
                case_id=record_case_id,
                document_id=str(record.get("document_id", "")),
                chunk_id=str(record.get("chunk_id", "")),
                text=str(record.get("text", "")),
                start_char=int(record.get("start_char", 0)),
                end_char=int(record.get("end_char", 0)),
                source=str(record.get("source", "provenance")),
                page=(
                    int(record["page"]) if isinstance(record.get("page"), int) else None
                ),
            )
            score = cosine_similarity(query_vector, vector)
            if min_score is not None and score < min_score:
                continue
            results.append(SearchResult(chunk=chunk, score=score))

        results.sort(
            key=lambda item: (
                -item.score,
                item.chunk.document_id,
                item.chunk.chunk_id,
            )
        )
        return results[:top_k]

    def case_stats(self, case_id: str) -> dict[str, object]:
        records = self._load_records()
        doc_counts: dict[str, int] = {}
        num_chunks = 0
        for record in records:
            if str(record.get("case_id", "")) != case_id:
                continue
            num_chunks += 1
            document_id = str(record.get("document_id", ""))
            doc_counts[document_id] = doc_counts.get(document_id, 0) + 1

        updated_at = None
        mtime = self._index_mtime()
        if mtime is not None:
            updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

        return {
            "num_chunks": num_chunks,
            "documents": [
                {"document_id": doc_id, "num_chunks": count}
                for doc_id, count in sorted(doc_counts.items())
            ],
            "updated_at": updated_at,
        }

    def delete_case(self, case_id: str) -> int:
        records = self._load_records()
        kept: list[dict[str, Any]] = []
        deleted = 0
        for record in records:
            if str(record.get("case_id", "")) == case_id:
                deleted += 1
            else:
                kept.append(record)

        self._write_records(kept)
        return deleted
