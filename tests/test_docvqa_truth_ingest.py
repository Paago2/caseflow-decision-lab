from caseflow.pipelines.docvqa_truth_ingest import (
    _build_docvqa_manifest_v1,
    _build_docvqa_ocr_source_v1,
    _build_docvqa_qas_v1,
)


def test_docvqa_ocr_source_shape():
    obj = _build_docvqa_ocr_source_v1(
        split="train",
        run_id="sample",
        doc_id="abc123",
        image_filename="abc123.jpg",
        image_sha256="x" * 64,
        content_type="image/jpeg",
        ocr_filename="abc123.json",
        ocr_sha256="y" * 64,
        ocr_obj={"words": []},
    )
    assert obj["schema_version"] == "ocr.source.v1"
    assert obj["dataset"] == "docvqa"
    assert obj["doc_id"] == "abc123"


def test_docvqa_qas_source_shape():
    obj = _build_docvqa_qas_v1(
        split="train",
        run_id="sample",
        qas_filename="train.json",
        qas_sha256="z" * 64,
        qas_obj={"data": []},
    )
    assert obj["schema_version"] == "qas.source.v1"
    assert obj["dataset"] == "docvqa"


def test_docvqa_manifest_shape():
    obj = _build_docvqa_manifest_v1(
        split="train",
        run_id="sample",
        rows=[{"doc_id": "abc123", "has_ocr": True}],
    )
    assert obj["schema_version"] == "manifest.v1"
    assert obj["count"] == 1
