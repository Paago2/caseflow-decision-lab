from caseflow.pipelines.synthdog_truth_ingest import (
    _build_dataset_info_source_v1,
    _build_manifest_v1,
)


def test_synthdog_dataset_info_shape():
    obj = _build_dataset_info_source_v1(
        run_id="sample",
        filename="dataset_infos.json",
        sha256="x" * 64,
        dataset_info_obj={"default": {}},
    )
    assert obj["schema_version"] == "dataset_info.source.v1"
    assert obj["dataset"] == "synthdog_en"


def test_synthdog_manifest_shape():
    obj = _build_manifest_v1(
        run_id="sample",
        rows=[{"relative_path": "part-0001"}],
    )
    assert obj["schema_version"] == "manifest.v1"
    assert obj["dataset"] == "synthdog_en"
    assert obj["count"] == 1
