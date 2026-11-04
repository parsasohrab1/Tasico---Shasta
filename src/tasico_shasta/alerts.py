from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SignalMeasurement:
    metric: str
    actual: float
    expected: float
    warning_threshold: float
    critical_threshold: float


def detect_deviations(
    *,
    factory_id: str,
    observed_at: datetime,
    signals: list[SignalMeasurement],
) -> list[dict[str, Any]]:
    alerts = []
    for signal in signals:
        actual = signal.actual
        expected = signal.expected
        deviation = actual - expected
        magnitude = abs(deviation)
        if magnitude < signal.warning_threshold:
            continue

        alerts.append(
            {
                "factory_id": factory_id,
                "observed_at": observed_at.isoformat(),
                "metric": signal.metric,
                "actual": actual,
                "expected": expected,
                "deviation": deviation,
                "deviation_percent": deviation / expected * 100 if expected else None,
                "warning_threshold": signal.warning_threshold,
                "critical_threshold": signal.critical_threshold,
                "direction": "above_expected" if deviation > 0 else "below_expected",
                "severity": (
                    "critical"
                    if magnitude >= signal.critical_threshold
                    else "warning"
                ),
                "status": "detected",
                "cause_assessment": "not_assessed",
            }
        )
    return alerts
