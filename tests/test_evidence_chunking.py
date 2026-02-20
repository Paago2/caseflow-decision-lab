from caseflow.domain.mortgage.evidence import chunk_text


def test_chunk_text_is_deterministic_with_expected_overlap() -> None:
    text = "0123456789" * 300

    chunks_a = chunk_text(
        case_id="case_1",
        document_id="doc_1",
        text=text,
        chunk_size=700,
        overlap=100,
    )
    chunks_b = chunk_text(
        case_id="case_1",
        document_id="doc_1",
        text=text,
        chunk_size=700,
        overlap=100,
    )

    assert len(chunks_a) == 5
    assert chunks_a == chunks_b
    assert chunks_a[0].start_char == 0
    assert chunks_a[0].end_char == 700
    assert chunks_a[1].start_char == 600
    assert chunks_a[1].end_char == 1300

    overlap_a = chunks_a[0].text[-100:]
    overlap_b = chunks_a[1].text[:100]
    assert overlap_a == overlap_b


def test_chunk_text_empty_input_returns_empty_list() -> None:
    assert chunk_text(case_id="case_1", document_id="doc_1", text="") == []
