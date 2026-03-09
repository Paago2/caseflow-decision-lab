from caseflow.pipelines.sroie_truth_ingest import (
    _build_sroie_boxes_source_v1,
    _build_sroie_entities_source_v1,
    _build_sroie_manifest_v1,
    _parse_sroie_box_text,
)


def test_parse_sroie_box_text():
    raw = "1,2,3,4,5,6,7,8,TOTAL"
    rows = _parse_sroie_box_text(raw)
    assert len(rows) == 1
    assert rows[0]["parsed"] is True
    assert rows[0]["text"] == "TOTAL"


def test_sroie_boxes_source_shape():
    obj = _build_sroie_boxes_source_v1(
        split="train",
        run_id="sample",
        doc_id="abc123",
        image_filename="abc123.jpg",
        image_sha256="x" * 64,
        content_type="image/jpeg",
        boxes_filename="abc123.txt",
        boxes_sha256="y" * 64,
        boxes_rows=[],
    )
    assert obj["schema_version"] == "boxes.source.v1"
    assert obj["dataset"] == "sroie"


def test_sroie_entities_source_shape():
    obj = _build_sroie_entities_source_v1(
        split="train",
        run_id="sample",
        doc_id="abc123",
        image_filename="abc123.jpg",
        image_sha256="x" * 64,
        content_type="image/jpeg",
        entities_filename="abc123.txt",
        entities_sha256="z" * 64,
        entities_obj={"company": "ABC"},
    )
    assert obj["schema_version"] == "entities.source.v1"
    assert obj["dataset"] == "sroie"


def test_sroie_manifest_shape():
    obj = _build_sroie_manifest_v1(
        split="train",
        run_id="sample",
        rows=[{"doc_id": "abc123"}],
    )
    assert obj["schema_version"] == "manifest.v1"
    assert obj["count"] == 1
