"""
مدل MILP بهینه‌سازی بهره‌برداری دیگ‌ها و توربین‌ها.
استفاده از PuLP با حل‌کننده CBC (پیش‌فرض) یا Gurobi (اختیاری).

مدل برای هر بازه زمانی (معمولاً 1 ساعت) حل می‌شود.
"""
from typing import Dict, List, Optional
import pulp
from pulp import LpStatus


def build_and_solve(
    steam_demand_tph: float,
    elec_demand_kw: float,
    boilers: List[dict],
    turbines: List[dict],
    gas_price: float = 0.15,
    elec_price_import: float = 0.16,
    elec_price_export: float = 0.04,
    steam_to_turbine_fraction: float = 0.30,
    solver_name: str = "PULP_CBC_CMD",
    time_limit_s: float = 10.0,
) -> dict:
    """
    ورودی‌ها:
        steam_demand_tph: تقاضای بخار (ton/h)
        elec_demand_kw: تقاضای برق (kWh برای بازه 1 ساعت = kW)
        boilers: [{id, cap_tph, eff, min_load(0..1)}]
        turbines: [{id, cap_mw, eff, min_load(0..1)}]

    خروجی:
        {status, total_cost, boiler_steam{id: tph}, boiler_gas{id: m3h},
         turbine_power{id: mw}, grid_import_kw, grid_export_kw}
    """
    n_b = len(boilers)
    n_t = len(turbines)

    # ---------------- Problem ----------------
    prob = pulp.LpProblem("CEUO_Optimization", pulp.LpMinimize)

    # ---------------- Variables ----------------
    y_b = {b["id"]: pulp.LpVariable(f"y_{b['id']}", cat="Binary") for b in boilers}
    s_b = {b["id"]: pulp.LpVariable(f"s_{b['id']}", lowBound=0) for b in boilers}
    g_b = {b["id"]: pulp.LpVariable(f"g_{b['id']}", lowBound=0) for b in boilers}

    y_t = {t["id"]: pulp.LpVariable(f"y_{t['id']}", cat="Binary") for t in turbines}
    p_t = {t["id"]: pulp.LpVariable(f"p_{t['id']}", lowBound=0) for t in turbines}

    grid_in = pulp.LpVariable("grid_import", lowBound=0)
    grid_out = pulp.LpVariable("grid_export", lowBound=0)

    # ---------------- Objective ----------------
    gas_cost = pulp.lpSum(g_b[b["id"]] * gas_price for b in boilers)
    elec_cost = grid_in * elec_price_import
    export_revenue = grid_out * elec_price_export
    prob += gas_cost + elec_cost - export_revenue

    # ---------------- Constraints ----------------
    # 1) تقاضای بخار
    prob += pulp.lpSum(s_b[b["id"]] for b in boilers) >= steam_demand_tph

    # 2) تقاضای برق
    prob += (pulp.lpSum(p_t[t["id"]] * 1000 for t in turbines)
             + grid_in - grid_out >= elec_demand_kw)

    # 3) محدودیت هر دیگ
    for b in boilers:
        cap = b["cap_tph"]
        min_load = b.get("min_load", 0.0)
        eff = b["eff"]
        # اگر خاموش: s=0، اگر روشن: بین min و max
        prob += s_b[b["id"]] <= cap * y_b[b["id"]]
        prob += s_b[b["id"]] >= cap * min_load * y_b[b["id"]]
        # گاز = بخار * 7.5 / راندمان
        prob += g_b[b["id"]] == s_b[b["id"]] * 7.5 / eff

    # 4) محدودیت هر توربین
    for t in turbines:
        cap_mw = t["cap_mw"]
        min_load = t.get("min_load", 0.0)
        eff = t["eff"]
        # رابطه بخار→توان: 1 ton/h ≈ 0.1 MW * eff/0.25
        # یعنی برای تولید p MW، به بخار ~ p / (0.1 * eff/0.25) نیاز است
        # اما برای سادگی، ظرفیت توان را مستقل مدل می‌کنیم
        prob += p_t[t["id"]] <= cap_mw * y_t[t["id"]]
        prob += p_t[t["id"]] >= cap_mw * min_load * y_t[t["id"]]

    # 5) مجموع بخار به توربین نمی‌تواند بیش از fraction کل باشد
    total_steam_to_turb = pulp.lpSum(p_t[t["id"]] for t in turbines) / 0.1  # ton/h
    prob += total_steam_to_turb <= steam_to_turbine_fraction * steam_demand_tph * 1.5

    # ---------------- Solve ----------------
    if solver_name == "PULP_CBC_CMD":
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s)
    elif solver_name == "GUROBI":
        try:
            solver = pulp.GUROBI_CMD(msg=False, timeLimit=time_limit_s)
        except Exception:
            solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s)
    else:
        solver = pulp.getSolver(solver_name)

    prob.solve(solver)

    # ---------------- Extract ----------------
    status = LpStatus[prob.status]
    result = {
        "status": status,
        "total_cost": 0.0,
        "boiler_steam": {},
        "boiler_gas": {},
        "turbine_power": {},
        "grid_import_kw": 0.0,
        "grid_export_kw": 0.0,
        "boiler_on": {},
        "turbine_on": {},
    }

    if status == "Optimal":
        result["total_cost"] = float(pulp.value(prob.objective))
        for b in boilers:
            bid = b["id"]
            result["boiler_steam"][bid] = float(s_b[bid].value() or 0)
            result["boiler_gas"][bid] = float(g_b[bid].value() or 0)
            result["boiler_on"][bid] = bool(round(y_b[bid].value() or 0))
        for t in turbines:
            tid = t["id"]
            result["turbine_power"][tid] = float(p_t[tid].value() or 0)
            result["turbine_on"][tid] = bool(round(y_t[tid].value() or 0))
        result["grid_import_kw"] = float(grid_in.value() or 0)
        result["grid_export_kw"] = float(grid_out.value() or 0)

    return result

"""اجرای بهینه‌سازی برای یک کارخانه + ذخیره نتیجه"""
from datetime import datetime
from typing import Dict, List
from optimization.milp_model import build_and_solve


FACTORY_CONFIG = {
    "F1-PAPER": {
        "boilers": [
            {"id": "B1", "cap_tph": 30, "eff": 0.88, "min_load": 0.20},
            {"id": "B2", "cap_tph": 25, "eff": 0.86, "min_load": 0.20},
        ],
        "turbines": [
            {"id": "T1", "cap_mw": 5.0, "eff": 0.28, "min_load": 0.30},
        ],
    },
    "F2-TISSUE": {
        "boilers": [
            {"id": "B1", "cap_tph": 20, "eff": 0.90, "min_load": 0.20},
            {"id": "B2", "cap_tph": 15, "eff": 0.87, "min_load": 0.20},
        ],
        "turbines": [
            {"id": "T1", "cap_mw": 3.0, "eff": 0.27, "min_load": 0.30},
        ],
    },
    "F3-WOOD": {
        "boilers": [
            {"id": "B1", "cap_tph": 25, "eff": 0.85, "min_load": 0.20},
            {"id": "B2", "cap_tph": 20, "eff": 0.83, "min_load": 0.20},
            {"id": "B3", "cap_tph": 15, "eff": 0.82, "min_load": 0.20},
        ],
        "turbines": [
            {"id": "T1", "cap_mw": 4.0, "eff": 0.26, "min_load": 0.30},
            {"id": "T2", "cap_mw": 3.0, "eff": 0.25, "min_load": 0.30},
        ],
    },
}


def optimize_factory(
    factory_id: str,
    steam_demand_tph: float,
    elec_demand_kw: float,
    gas_price: float = 0.15,
    elec_price_import: float = 0.16,
    elec_price_export: float = 0.04,
) -> dict:
    """بهینه‌سازی یک بازه برای یک کارخانه"""
    if factory_id not in FACTORY_CONFIG:
        raise ValueError(f"unknown factory: {factory_id}")
    cfg = FACTORY_CONFIG[factory_id]

    result = build_and_solve(
        steam_demand_tph=steam_demand_tph,
        elec_demand_kw=elec_demand_kw,
        boilers=cfg["boilers"],
        turbines=cfg["turbines"],
        gas_price=gas_price,
        elec_price_import=elec_price_import,
        elec_price_export=elec_price_export,
    )
    result["factory_id"] = factory_id
    result["timestamp"] = datetime.utcnow().isoformat()
    result["input"] = {
        "steam_demand_tph": steam_demand_tph,
        "elec_demand_kw": elec_demand_kw,
        "gas_price": gas_price,
        "elec_price_import": elec_price_import,
    }
    return result


def optimize_batch(factory_id: str, rows: List[dict]) -> List[dict]:
    """بهینه‌سازی چند بازه پشت سر هم"""
    out = []
    for r in rows:
        try:
            out.append(optimize_factory(
                factory_id,
                steam_demand_tph=r["steam_demand_t"],
                elec_demand_kw=r["elec_consumption_kwh"],
                gas_price=r.get("gas_price", 0.15),
                elec_price_import=r.get("elec_price", 0.16),
            ))
        except Exception as e:
            out.append({"status": "Error", "error": str(e), "factory_id": factory_id})
    return out

"""تحلیل سناریو: مقایسه baseline با بهینه"""
from typing import List
from optimization.engine import optimize_factory


def compare_baseline_vs_optimal(factory_id: str, rows: List[dict]) -> dict:
    """
    rows: [{timestamp, steam_demand_t, elec_consumption_kwh,
            gas_consumption_m3, grid_import_kwh, gas_price, elec_price}]
    """
    baseline_cost = 0.0
    optimal_cost = 0.0
    details = []

    for r in rows:
        gas_price = r.get("gas_price", 0.15)
        elec_price = r.get("elec_price", 0.16)

        # هزینه baseline (واقعی)
        b_cost = (r["gas_consumption_m3"] * gas_price
                  + r["grid_import_kwh"] * elec_price)
        baseline_cost += b_cost

        # هزینه بهینه
        opt = optimize_factory(
            factory_id,
            steam_demand_tph=r["steam_demand_t"],
            elec_demand_kw=r["elec_consumption_kwh"],
            gas_price=gas_price,
            elec_price_import=elec_price,
        )
        o_cost = opt.get("total_cost", 0)
        optimal_cost += o_cost

        details.append({
            "timestamp": r.get("timestamp"),
            "baseline_cost": b_cost,
            "optimal_cost": o_cost,
            "savings": b_cost - o_cost,
            "status": opt.get("status"),
        })

    return {
        "factory_id": factory_id,
        "n_periods": len(rows),
        "baseline_cost": round(baseline_cost, 2),
        "optimal_cost": round(optimal_cost, 2),
        "savings": round(baseline_cost - optimal_cost, 2),
        "savings_pct": round(
            (baseline_cost - optimal_cost) / baseline_cost * 100, 2
        ) if baseline_cost else 0.0,
        "details": details,
    }

# app.py — در page_optimization، جایگزین شبیه‌سازی:
from optimization.engine import optimize_factory

if st.button("🚀 اجرای بهینه‌سازی MILP", type="primary"):
    with st.spinner("حل مدل MILP با CBC…"):
        try:
            recent = df[df["timestamp"] > df["timestamp"].max() - timedelta(days=1)]
            row = recent.iloc[-1]
            result = optimize_factory(
                factory_id=row["factory_id"],
                steam_demand_tph=float(row["steam_demand_t"]),
                elec_demand_kw=float(row["elec_consumption_kwh"]),
                gas_price=gas_price,
                elec_price_import=elec_peak,
            )
            if result["status"] == "Optimal":
                st.success(f"بهینه‌سازی موفق — هزینه بهینه: ${result['total_cost']:,.2f}")
                st.json(result)
            else:
                st.warning(f"وضعیت: {result['status']}")
        except Exception as e:
            st.error(f"خطا: {e}")

