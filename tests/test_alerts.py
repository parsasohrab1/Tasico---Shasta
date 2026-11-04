from datetime import datetime, timezone

from tasico_shasta.alerts import SignalMeasurement, detect_deviations


def test_deviation_alerts_apply_explicit_thresholds_and_severity() -> None:
    alerts = detect_deviations(
        factory_id="F1",
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        signals=[
            SignalMeasurement("gas_consumption_m3", 125, 100, 10, 25),
            SignalMeasurement("water_intake_m3", 104, 100, 5, 20),
        ],
    )

    assert len(alerts) == 1
    assert alerts[0]["metric"] == "gas_consumption_m3"
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["deviation"] == 25
    assert alerts[0]["deviation_percent"] == 25
    assert alerts[0]["critical_threshold"] == 25
    assert alerts[0]["direction"] == "above_expected"
    assert alerts[0]["status"] == "detected"
    assert alerts[0]["cause_assessment"] == "not_assessed"


def test_deviation_alert_supports_zero_expected_value_and_underuse() -> None:
    alerts = detect_deviations(
        factory_id="F1",
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        signals=[
            SignalMeasurement("steam_demand_t", 0, 10, 2, 5),
            SignalMeasurement("elec_consumption_kwh", 3, 0, 2, 5),
        ],
    )

    assert len(alerts) == 2
    assert alerts[0]["direction"] == "below_expected"
    assert alerts[0]["deviation_percent"] == -100
    assert alerts[1]["deviation_percent"] is None
    assert alerts[1]["severity"] == "warning"
