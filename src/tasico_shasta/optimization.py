from __future__ import annotations

import math
from typing import Any

import pulp


def solve_dispatch(
    *,
    steam_demand_tph: float,
    electricity_demand_kw: float,
    boilers: list[dict[str, Any]],
    turbines: list[dict[str, Any]],
    gas_price_per_m3: float,
    electricity_import_price_per_kwh: float,
    electricity_export_price_per_kwh: float = 0.0,
    interval_hours: float = 1.0,
    time_limit_seconds: float = 10.0,
) -> dict[str, Any]:
    """Return a cost-minimizing dispatch; this function never writes to plant controls.

    Boiler fuel intensity and turbine steam intensity are plant-specific, calibrated
    inputs. They are deliberately required rather than guessed from generic defaults.
    """
    _validate_inputs(
        steam_demand_tph=steam_demand_tph,
        electricity_demand_kw=electricity_demand_kw,
        boilers=boilers,
        turbines=turbines,
        gas_price_per_m3=gas_price_per_m3,
        electricity_import_price_per_kwh=electricity_import_price_per_kwh,
        electricity_export_price_per_kwh=electricity_export_price_per_kwh,
        interval_hours=interval_hours,
        time_limit_seconds=time_limit_seconds,
    )
    if not pulp.listSolvers(onlyAvailable=True):
        raise RuntimeError("No PuLP solver is installed; install a CBC-compatible PuLP build")

    problem = pulp.LpProblem("tasico_dispatch", pulp.LpMinimize)
    boiler_on = {
        f"boiler_{index}": pulp.LpVariable(f"boiler_on_{index}", cat=pulp.LpBinary)
        for index in range(len(boilers))
    }
    boiler_steam = {
        f"boiler_{index}": pulp.LpVariable(f"boiler_steam_{index}", lowBound=0)
        for index in range(len(boilers))
    }
    boiler_gas = {
        f"boiler_{index}": pulp.LpVariable(f"boiler_gas_{index}", lowBound=0)
        for index in range(len(boilers))
    }
    turbine_on = {
        f"turbine_{index}": pulp.LpVariable(f"turbine_on_{index}", cat=pulp.LpBinary)
        for index in range(len(turbines))
    }
    turbine_power = {
        f"turbine_{index}": pulp.LpVariable(f"turbine_power_{index}", lowBound=0)
        for index in range(len(turbines))
    }
    grid_mode = pulp.LpVariable("grid_import_mode", cat=pulp.LpBinary)
    grid_import_kw = pulp.LpVariable("grid_import_kw", lowBound=0)
    grid_export_kw = pulp.LpVariable("grid_export_kw", lowBound=0)
    steam_dump_tph = pulp.LpVariable("steam_dump_tph", lowBound=0)

    problem += interval_hours * (
        pulp.lpSum(boiler_gas.values()) * gas_price_per_m3
        + grid_import_kw * electricity_import_price_per_kwh
        - grid_export_kw * electricity_export_price_per_kwh
    )

    for index, boiler in enumerate(boilers):
        key = f"boiler_{index}"
        problem += boiler_steam[key] <= boiler["capacity_tph"] * boiler_on[key]
        problem += (
            boiler_steam[key]
            >= boiler["capacity_tph"] * boiler["minimum_load"] * boiler_on[key]
        )
        problem += (
            boiler_gas[key]
            == boiler_steam[key] * boiler["gas_m3_per_tonne_steam"]
        )

    for index, turbine in enumerate(turbines):
        key = f"turbine_{index}"
        problem += turbine_power[key] <= turbine["capacity_mw"] * turbine_on[key]
        problem += (
            turbine_power[key]
            >= turbine["capacity_mw"] * turbine["minimum_load"] * turbine_on[key]
        )

    turbine_steam = pulp.lpSum(
        turbine_power[f"turbine_{index}"] * turbine["steam_tonnes_per_mwh"]
        for index, turbine in enumerate(turbines)
    )
    problem += pulp.lpSum(boiler_steam.values()) == (
        steam_demand_tph + turbine_steam + steam_dump_tph
    )
    problem += (
        pulp.lpSum(power * 1000 for power in turbine_power.values())
        + grid_import_kw
        - grid_export_kw
        == electricity_demand_kw
    )

    max_import_kw = electricity_demand_kw
    max_export_kw = max(
        0.0,
        sum(turbine["capacity_mw"] * 1000 for turbine in turbines)
        - electricity_demand_kw,
    )
    problem += grid_import_kw <= max_import_kw * grid_mode
    problem += grid_export_kw <= max_export_kw * (1 - grid_mode)

    status_code = problem.solve(
        pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_seconds)
    )
    status = pulp.LpStatus[status_code]
    result: dict[str, Any] = {
        "status": status,
        "interval_hours": interval_hours,
        "total_cost": None,
        "boiler_steam_tph": {},
        "boiler_gas_m3_per_hour": {},
        "turbine_power_mw": {},
        "grid_import_kw": None,
        "grid_export_kw": None,
        "steam_dump_tph": None,
    }
    if status != "Optimal":
        return result

    result["total_cost"] = float(pulp.value(problem.objective))
    result["boiler_steam_tph"] = {
        boiler["id"]: _value(boiler_steam[f"boiler_{index}"])
        for index, boiler in enumerate(boilers)
    }
    result["boiler_gas_m3_per_hour"] = {
        boiler["id"]: _value(boiler_gas[f"boiler_{index}"])
        for index, boiler in enumerate(boilers)
    }
    result["turbine_power_mw"] = {
        turbine["id"]: _value(turbine_power[f"turbine_{index}"])
        for index, turbine in enumerate(turbines)
    }
    result["grid_import_kw"] = _value(grid_import_kw)
    result["grid_export_kw"] = _value(grid_export_kw)
    result["steam_dump_tph"] = _value(steam_dump_tph)
    return result


def backtest_savings(
    rows: list[dict[str, Any]],
    equipment_by_factory: dict[str, dict[str, list[dict[str, Any]]]],
    *,
    interval_hours: float = 1.0,
) -> dict[str, Any]:
    """Compare actual held-out energy bills with a modeled dispatch counterfactual."""
    if not rows:
        raise ValueError("the held-out dataset must contain at least one row")
    if not math.isfinite(interval_hours) or interval_hours <= 0:
        raise ValueError("interval_hours must be a finite positive number")

    baseline_total = 0.0
    modeled_total = 0.0
    for row_number, row in enumerate(rows, start=1):
        factory_id = row.get("factory_id")
        if factory_id not in equipment_by_factory:
            raise ValueError(f"row {row_number}: no calibrated equipment for {factory_id!r}")
        try:
            actual_gas = _non_negative(row["actual_gas_m3"], "actual_gas_m3")
            actual_import = _non_negative(
                row["actual_grid_import_kwh"], "actual_grid_import_kwh"
            )
            actual_export = _non_negative(
                row.get("actual_grid_export_kwh", 0.0), "actual_grid_export_kwh"
            )
            gas_price = _non_negative(row["gas_price_per_m3"], "gas_price_per_m3")
            import_price = _non_negative(
                row["electricity_import_price_per_kwh"],
                "electricity_import_price_per_kwh",
            )
            export_price = _non_negative(
                row.get("electricity_export_price_per_kwh", 0.0),
                "electricity_export_price_per_kwh",
            )
            if export_price > import_price:
                raise ValueError("electricity export price exceeds import price")
            baseline = (
                actual_gas * gas_price
                + actual_import * import_price
                - actual_export * export_price
            )
            result = solve_dispatch(
                steam_demand_tph=float(row["steam_demand_tph"]),
                electricity_demand_kw=float(row["electricity_demand_kw"]),
                boilers=equipment_by_factory[factory_id]["boilers"],
                turbines=equipment_by_factory[factory_id].get("turbines", []),
                gas_price_per_m3=gas_price,
                electricity_import_price_per_kwh=import_price,
                electricity_export_price_per_kwh=export_price,
                interval_hours=interval_hours,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"row {row_number}: invalid savings input: {exc}") from exc
        if not math.isfinite(baseline):
            raise ValueError(f"row {row_number}: actual baseline cost must be finite")
        if result["status"] != "Optimal":
            raise ValueError(f"row {row_number}: dispatch model returned {result['status']}")
        baseline_total += baseline
        modeled_total += result["total_cost"]

    savings = baseline_total - modeled_total
    return {
        "claim_type": "counterfactual_modeled_potential",
        "measured_realized_savings": False,
        "row_count": len(rows),
        "baseline_cost": baseline_total,
        "modeled_optimal_cost": modeled_total,
        "modeled_potential_savings": savings,
        "modeled_potential_savings_percent": (
            100 * savings / baseline_total if baseline_total > 0 else None
        ),
    }


def _validate_inputs(
    *,
    steam_demand_tph: float,
    electricity_demand_kw: float,
    boilers: list[dict[str, Any]],
    turbines: list[dict[str, Any]],
    gas_price_per_m3: float,
    electricity_import_price_per_kwh: float,
    electricity_export_price_per_kwh: float,
    interval_hours: float,
    time_limit_seconds: float,
) -> None:
    numeric_inputs = {
        "steam_demand_tph": steam_demand_tph,
        "electricity_demand_kw": electricity_demand_kw,
        "gas_price_per_m3": gas_price_per_m3,
        "electricity_import_price_per_kwh": electricity_import_price_per_kwh,
        "electricity_export_price_per_kwh": electricity_export_price_per_kwh,
        "interval_hours": interval_hours,
        "time_limit_seconds": time_limit_seconds,
    }
    for name, value in numeric_inputs.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if steam_demand_tph < 0 or electricity_demand_kw < 0:
        raise ValueError("energy demands must be non-negative")
    if gas_price_per_m3 < 0 or electricity_import_price_per_kwh < 0:
        raise ValueError("import prices must be non-negative")
    if electricity_export_price_per_kwh < 0:
        raise ValueError("export price must be non-negative")
    if electricity_export_price_per_kwh > electricity_import_price_per_kwh:
        raise ValueError("export price cannot exceed import price")
    if interval_hours <= 0 or time_limit_seconds <= 0:
        raise ValueError("interval_hours and time_limit_seconds must be positive")
    if not boilers:
        raise ValueError("at least one boiler must be configured")

    for equipment_type, equipment in (("boiler", boilers), ("turbine", turbines)):
        identifiers: set[str] = set()
        for index, item in enumerate(equipment):
            if not isinstance(item, dict):
                raise ValueError(f"{equipment_type} {index} must be an object")
            identifier = item.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError(f"{equipment_type} {index} needs a non-empty id")
            if identifier in identifiers:
                raise ValueError(f"duplicate {equipment_type} id: {identifier}")
            identifiers.add(identifier)
            capacity_key = "capacity_tph" if equipment_type == "boiler" else "capacity_mw"
            intensity_key = (
                "gas_m3_per_tonne_steam"
                if equipment_type == "boiler"
                else "steam_tonnes_per_mwh"
            )
            for key in (capacity_key, intensity_key):
                value = item.get(key)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value <= 0
                ):
                    raise ValueError(f"{equipment_type} {identifier} needs positive {key}")
            minimum_load = item.get("minimum_load", 0.0)
            if (
                isinstance(minimum_load, bool)
                or not isinstance(minimum_load, (int, float))
                or not math.isfinite(minimum_load)
                or not 0 <= minimum_load <= 1
            ):
                raise ValueError(f"{equipment_type} {identifier} minimum_load must be in [0, 1]")


def _value(variable: pulp.LpVariable) -> float:
    value = variable.value()
    if value is None:
        raise RuntimeError(f"solver returned an empty value for {variable.name}")
    return float(value)


def _non_negative(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite non-negative number")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite non-negative number") from exc
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return numeric
