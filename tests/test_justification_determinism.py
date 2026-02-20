from caseflow.domain.mortgage.evidence import EvidenceChunk
from caseflow.domain.mortgage.justification import generate_deterministic_justification
from caseflow.ml.vector_store import SearchResult


def test_justification_generation_is_deterministic() -> None:
    evidence = [
        SearchResult(
            chunk=EvidenceChunk(
                case_id="case_1",
                document_id="doc_a",
                chunk_id="chunk_a",
                text="income stability evidence",
                start_char=0,
                end_char=25,
                source="provenance",
                page=None,
            ),
            score=0.9,
        ),
        SearchResult(
            chunk=EvidenceChunk(
                case_id="case_1",
                document_id="doc_b",
                chunk_id="chunk_b",
                text="debt obligations evidence",
                start_char=10,
                end_char=35,
                source="provenance",
                page=None,
            ),
            score=0.7,
        ),
    ]

    j1 = generate_deterministic_justification(
        decision="review",
        policy_reasons=["REVIEW_DTI_BORDERLINE"],
        risk_score=150.0,
        evidence_results=evidence,
    )
    j2 = generate_deterministic_justification(
        decision="review",
        policy_reasons=["REVIEW_DTI_BORDERLINE"],
        risk_score=150.0,
        evidence_results=evidence,
    )

    assert j1 == j2
    assert j1.citations[0].chunk_id == "chunk_a"
    assert any("C1" in reason for reason in j1.reasons)
