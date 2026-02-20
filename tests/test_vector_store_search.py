from pathlib import Path

from caseflow.domain.mortgage.evidence import EvidenceChunk
from caseflow.ml.vector_store import FileVectorStore


def test_vector_store_search_orders_results_deterministically(tmp_path: Path) -> None:
    store = FileVectorStore(index_file=tmp_path / "index.json")
    chunks = [
        EvidenceChunk(
            case_id="case_1",
            document_id="doc_a",
            chunk_id="c1",
            text="borrower income is strong and stable",
            start_char=0,
            end_char=36,
            source="provenance",
            page=None,
        ),
        EvidenceChunk(
            case_id="case_1",
            document_id="doc_b",
            chunk_id="c2",
            text="credit score improved over the last year",
            start_char=0,
            end_char=39,
            source="provenance",
            page=None,
        ),
        EvidenceChunk(
            case_id="case_2",
            document_id="doc_c",
            chunk_id="c3",
            text="unrelated collateral appraisal notes",
            start_char=0,
            end_char=35,
            source="provenance",
            page=None,
        ),
    ]

    assert store.add_documents(chunks) == 3

    results = store.search("income", top_k=2, case_id="case_1")
    assert len(results) == 2
    assert results[0].chunk.document_id == "doc_a"
    assert results[0].score >= results[1].score

    results_again = store.search("income", top_k=2, case_id="case_1")
    assert [item.chunk.chunk_id for item in results] == [
        item.chunk.chunk_id for item in results_again
    ]
