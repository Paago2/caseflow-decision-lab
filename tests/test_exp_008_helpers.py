import pytest

from caseflow.ml.exp_008_helpers import (
    build_schema_v2,
    select_winner_by_rmse_then_mae,
)


def test_select_winner_by_rmse_then_mae_prefers_lower_rmse_then_mae() -> None:
    winner = select_winner_by_rmse_then_mae(
        {
            "linear_regression": {"rmse": 55.0, "mae": 44.0},
            "scaled_ridge": {"rmse": 55.0, "mae": 43.0},
        }
    )

    assert winner == "scaled_ridge"


def test_build_schema_v2_marks_required_and_optional_defaults() -> None:
    schema = build_schema_v2(
        ["age", "sex", "bmi", "bp", "s1", "s2", "s3", "s4", "s5", "s6"]
    )

    assert schema["schema_version"] == "2"
    features = schema["features"]
    assert len(features) == 10

    required_map = {item["name"]: item["required"] for item in features}
    assert required_map["age"] is True
    assert required_map["sex"] is True
    assert required_map["bmi"] is True
    assert required_map["bp"] is True
    assert required_map["s1"] is False

    optional_s1 = next(item for item in features if item["name"] == "s1")
    assert optional_s1["default"] == 0.0


def test_build_schema_v2_rejects_missing_required_columns() -> None:
    with pytest.raises(ValueError) as exc_info:
        build_schema_v2(["sex", "bmi", "bp", "s1"])

    assert "missing required schema v2 names" in str(exc_info.value)
    assert "age" in str(exc_info.value)
