import numpy as np
import pandas as pd
import pytest

from tasico_shasta.modeling import TARGET_COLUMNS, build_features, evaluate_dataset


def example_frame(rows: int = 40) -> pd.DataFrame:
    timestamps = pd.date_range("2025-01-01", periods=rows, freq="h", tz="UTC")
    data = {
        "timestamp": timestamps,
        "factory_id": ["F1"] * rows,
        "production_t": np.arange(rows, dtype=float) + 10,
    }
    for index, target in enumerate(TARGET_COLUMNS):
        data[target] = np.arange(rows, dtype=float) + 100 + index
    return pd.DataFrame(data)


def test_rolling_features_exclude_the_current_observation() -> None:
    source = example_frame(30)
    engineered = build_features(source)
    assert engineered.loc[24, f"{TARGET_COLUMNS[0]}_rolling_24_mean"] == pytest.approx(
        source.loc[0:23, TARGET_COLUMNS[0]].mean()
    )
    changed = source.copy()
    changed.loc[24, TARGET_COLUMNS[0]] = 100000
    rebuilt = build_features(changed)
    assert (
        rebuilt.loc[24, f"{TARGET_COLUMNS[0]}_rolling_24_mean"]
        == engineered.loc[24, f"{TARGET_COLUMNS[0]}_rolling_24_mean"]
    )


def test_dataset_split_is_chronological_and_reports_observed_rows() -> None:
    report = evaluate_dataset(example_frame(), test_fraction=0.25)
    factory = report["factories"]["F1"]
    assert report["report_type"] == "chronological_one_step_ahead_backtest"
    assert report["dataset_authenticity"] == "not_independently_verified"
    assert factory["train_rows"] == 30
    assert factory["test_rows"] == 10
    assert factory["train_end"] < factory["test_start"]
    assert report["test_row_count"] == 10
    assert set(factory["targets"]) == set(TARGET_COLUMNS)


def test_feature_builder_rejects_duplicate_factory_timestamps() -> None:
    frame = example_frame(10)
    frame.loc[9, "timestamp"] = frame.loc[8, "timestamp"]
    with pytest.raises(ValueError, match="duplicate"):
        build_features(frame)


def test_feature_builder_rejects_an_empty_dataset() -> None:
    with pytest.raises(ValueError, match="at least one observation"):
        build_features(example_frame(0))


def test_mape_excludes_zero_targets_and_uses_wape() -> None:
    frame = example_frame(20)
    frame.loc[19, TARGET_COLUMNS[0]] = 0
    report = evaluate_dataset(frame)
    metrics = report["factories"]["F1"]["targets"][TARGET_COLUMNS[0]]
    assert metrics["mape_sample_count"] == 3
    assert metrics["mape_percent"] is not None
    assert metrics["wape_percent"] is not None
