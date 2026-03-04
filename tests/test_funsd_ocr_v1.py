from caseflow.pipelines.funsd_ocr_ingest import (
    build_ocr_v1_json,
    build_truth_funsd_v1_json,
    doc_id_from_bytes,
)


def test_doc_id_deterministic():
    b = b"hello world"
    assert doc_id_from_bytes(b) == doc_id_from_bytes(b)
    assert len(doc_id_from_bytes(b)) == 16


def test_ocr_schema_shape_noop():
    o = build_ocr_v1_json(
        split="training",
        run_id="sample",
        doc_id="abcd" * 4,
        filename="0001.png",
        sha256="x" * 64,
        content_type="image/png",
        engine="noop",
        text="",
        duration_ms=1,
    )
    assert o["schema_version"] == "ocr.v1"
    assert o["dataset"] == "funsd"
    assert o["split"] == "training"
    assert o["run_id"] == "sample"
    assert o["doc_id"]
    assert o["source"]["filename"] == "0001.png"
    assert "ocr" in o
    assert o["ocr"]["engine"] == "noop"
    assert isinstance(o["ocr"]["pages"], list)
    assert o["ocr"]["pages"][0]["page"] == 1


def test_truth_schema_shape():
    t = build_truth_funsd_v1_json(
        split="training",
        run_id="sample",
        doc_id="abcd" * 4,
        filename="0001.json",
        sha256="y" * 64,
        truth_obj={"form": []},
    )
    assert t["schema_version"] == "truth.funsd.v1"
    assert t["dataset"] == "funsd"
    assert "truth" in t
    assert t["truth"]["form"] == []
