from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

TARGET_COLUMNS = (
    "elec_consumption_kwh",
    "steam_demand_t",
    "gas_consumption_m3",
    "water_intake_m3",
)
LAG_COLUMNS = (*TARGET_COLUMNS, "production_t")
KNOWN_AHEAD_COLUMNS = ("planned_production_t",)


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Create one-step-ahead features using past observations only."""
    if frame.empty:
        raise ValueError("dataset must contain at least one observation")
    required = {"timestamp", "factory_id", *TARGET_COLUMNS}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"dataset is missing columns: {', '.join(sorted(missing))}")

    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True, errors="raise")
    if result["factory_id"].isna().any() or (result["factory_id"].astype(str).str.strip() == "").any():
        raise ValueError("factory_id must be present on every row")
    if result.duplicated(["factory_id", "timestamp"]).any():
        raise ValueError("dataset contains duplicate factory_id/timestamp rows")
    result = result.sort_values(["factory_id", "timestamp"]).reset_index(drop=True)

    for column in (*TARGET_COLUMNS, "production_t", *KNOWN_AHEAD_COLUMNS):
        if column in result:
            numeric = pd.to_numeric(result[column], errors="raise")
            if not np.isfinite(numeric.dropna()).all():
                raise ValueError(f"{column} contains non-finite values")
            if (numeric.dropna() < 0).any():
                raise ValueError(f"{column} contains negative values")
            result[column] = numeric

    timestamps = result["timestamp"]
    result["hour_sin"] = np.sin(2 * np.pi * timestamps.dt.hour / 24)
    result["hour_cos"] = np.cos(2 * np.pi * timestamps.dt.hour / 24)
    result["weekday_sin"] = np.sin(2 * np.pi * timestamps.dt.dayofweek / 7)
    result["weekday_cos"] = np.cos(2 * np.pi * timestamps.dt.dayofweek / 7)
    result["year_day_sin"] = np.sin(2 * np.pi * timestamps.dt.dayofyear / 365.25)
    result["year_day_cos"] = np.cos(2 * np.pi * timestamps.dt.dayofyear / 365.25)

    for column in LAG_COLUMNS:
        if column not in result:
            continue
        grouped = result.groupby("factory_id", sort=False)[column]
        for lag in (1, 24, 168):
            result[f"{column}_lag_{lag}"] = grouped.shift(lag)
        previous = grouped.shift(1)
        for window in (24, 168):
            previous_grouped = previous.groupby(result["factory_id"], sort=False)
            result[f"{column}_rolling_{window}_mean"] = previous_grouped.transform(
                lambda values: values.rolling(window, min_periods=1).mean()
            )
    return result


def evaluate_dataset(
    frame: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
    model_directory: str | Path | None = None,
) -> dict[str, Any]:
    if not math.isfinite(test_fraction) or not 0 < test_fraction < 0.5:
        raise ValueError("test_fraction must be between 0 and 0.5")
    features_frame = build_features(frame)
    feature_columns = [
        column
        for column in features_frame.columns
        if column.startswith(("hour_", "weekday_", "year_day_"))
        or "_lag_" in column
        or "_rolling_" in column
        or column in KNOWN_AHEAD_COLUMNS
    ]
    if model_directory is not None:
        Path(model_directory).mkdir(parents=True, exist_ok=True)

    metrics: dict[str, dict[str, Any]] = {}
    total_train_rows = 0
    total_test_rows = 0
    for factory_id, factory_frame in features_frame.groupby("factory_id", sort=True):
        factory_frame = factory_frame.sort_values("timestamp")
        split_index = int(len(factory_frame) * (1 - test_fraction))
        if split_index < 2 or len(factory_frame) - split_index < 2:
            raise ValueError(f"factory {factory_id!r} needs at least four rows for a time split")
        training = factory_frame.iloc[:split_index]
        testing = factory_frame.iloc[split_index:]
        total_train_rows += len(training)
        total_test_rows += len(testing)
        factory_metrics: dict[str, Any] = {
            "train_rows": len(training),
            "test_rows": len(testing),
            "train_end": training["timestamp"].max().isoformat(),
            "test_start": testing["timestamp"].min().isoformat(),
            "targets": {},
        }

        for target in TARGET_COLUMNS:
            train_target = training[target].to_numpy(dtype=float)
            test_target = testing[target].to_numpy(dtype=float)
            if not np.isfinite(train_target).all() or not np.isfinite(test_target).all():
                raise ValueError(f"{target} contains missing or non-finite target values")

            model = HistGradientBoostingRegressor(
                max_iter=100,
                learning_rate=0.08,
                l2_regularization=1.0,
                random_state=42,
            )
            model.fit(training[feature_columns], train_target)
            predictions = np.maximum(0, model.predict(testing[feature_columns]))
            nonzero = test_target != 0
            absolute_errors = np.abs(test_target - predictions)
            actual_sum = float(np.abs(test_target).sum())
            target_metrics = {
                "mae": float(mean_absolute_error(test_target, predictions)),
                "rmse": float(np.sqrt(mean_squared_error(test_target, predictions))),
                "mape_percent": (
                    float(np.mean(absolute_errors[nonzero] / np.abs(test_target[nonzero])) * 100)
                    if nonzero.any()
                    else None
                ),
                "mape_sample_count": int(nonzero.sum()),
                "wape_percent": (
                    float(absolute_errors.sum() / actual_sum * 100) if actual_sum else None
                ),
                "r2": (
                    float(r2_score(test_target, predictions))
                    if len(test_target) > 1 and np.ptp(test_target) > 0
                    else None
                ),
            }
            factory_metrics["targets"][target] = target_metrics
            if model_directory is not None:
                model_name = hashlib.sha256(
                    f"{factory_id}\0{target}".encode("utf-8")
                ).hexdigest()[:20]
                joblib.dump(
                    {
                        "model": model,
                        "features": feature_columns,
                        "factory_id": factory_id,
                        "target": target,
                    },
                    Path(model_directory) / f"{model_name}.joblib",
                )
        metrics[str(factory_id)] = factory_metrics

    return {
        "report_type": "chronological_one_step_ahead_backtest",
        "dataset_authenticity": "not_independently_verified",
        "test_fraction": test_fraction,
        "train_row_count": total_train_rows,
        "test_row_count": total_test_rows,
        "feature_columns": feature_columns,
        "factories": metrics,
    }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
