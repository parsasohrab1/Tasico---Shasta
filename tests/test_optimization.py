import pytest

from tasico_shasta.optimization import backtest_savings, solve_dispatch


def boiler(capacity_tph: float = 20) -> dict:
    return {
        "id": "B1",
        "capacity_tph": capacity_tph,
        "gas_m3_per_tonne_steam": 2,
        "minimum_load": 0,
    }


def test_reference_dispatch_matches_hand_calculated_cost() -> None:
    result = solve_dispatch(
        steam_demand_tph=10,
        electricity_demand_kw=100,
        boilers=[boiler()],
        turbines=[],
        gas_price_per_m3=0.1,
        electricity_import_price_per_kwh=0.2,
    )
    assert result["status"] == "Optimal"
    assert result["boiler_steam_tph"]["B1"] == pytest.approx(10)
    assert result["boiler_gas_m3_per_hour"]["B1"] == pytest.approx(20)
    assert result["grid_import_kw"] == pytest.approx(100)
    assert result["grid_export_kw"] == pytest.approx(0)
    assert result["total_cost"] == pytest.approx(22)


def test_turbine_power_is_coupled_to_steam_balance() -> None:
    result = solve_dispatch(
        steam_demand_tph=10,
        electricity_demand_kw=500,
        boilers=[boiler(capacity_tph=20)],
        turbines=[
            {
                "id": "T1",
                "capacity_mw": 1,
                "steam_tonnes_per_mwh": 2,
                "minimum_load": 0,
            }
        ],
        gas_price_per_m3=0.1,
        electricity_import_price_per_kwh=0.2,
    )
    assert result["status"] == "Optimal"
    assert result["turbine_power_mw"]["T1"] == pytest.approx(0.5)
    assert result["boiler_steam_tph"]["B1"] == pytest.approx(11)
    assert result["grid_import_kw"] == pytest.approx(0)
    assert result["boiler_gas_m3_per_hour"]["B1"] == pytest.approx(22)
    assert result["total_cost"] == pytest.approx(2.2)


def test_infeasible_steam_capacity_is_not_reported_as_a_saving() -> None:
    result = solve_dispatch(
        steam_demand_tph=21,
        electricity_demand_kw=0,
        boilers=[boiler(capacity_tph=20)],
        turbines=[],
        gas_price_per_m3=0.1,
        electricity_import_price_per_kwh=0.2,
    )
    assert result["status"] == "Infeasible"
    assert result["total_cost"] is None


def test_backtest_labels_counterfactual_and_uses_measured_baseline() -> None:
    report = backtest_savings(
        [
            {
                "factory_id": "F1",
                "steam_demand_tph": 10,
                "electricity_demand_kw": 100,
                "actual_gas_m3": 30,
                "actual_grid_import_kwh": 100,
                "gas_price_per_m3": 0.1,
                "electricity_import_price_per_kwh": 0.2,
            }
        ],
        {"F1": {"boilers": [boiler()], "turbines": []}},
    )
    assert report["claim_type"] == "counterfactual_modeled_potential"
    assert report["measured_realized_savings"] is False
    assert report["baseline_cost"] == pytest.approx(23)
    assert report["modeled_optimal_cost"] == pytest.approx(22)
    assert report["modeled_potential_savings"] == pytest.approx(1)


def test_bad_equipment_intensity_is_rejected() -> None:
    with pytest.raises(ValueError, match="gas_m3_per_tonne_steam"):
        solve_dispatch(
            steam_demand_tph=1,
            electricity_demand_kw=0,
            boilers=[{"id": "B1", "capacity_tph": 1, "minimum_load": 0}],
            turbines=[],
            gas_price_per_m3=1,
            electricity_import_price_per_kwh=1,
        )
