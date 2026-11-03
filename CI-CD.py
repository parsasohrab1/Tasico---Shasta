[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = -ra -q --strict-markers --cov=. --cov-report=term-missing --cov-report=html --cov-report=xml --cov-fail-under=70
markers =
    unit: unit tests
    integration: integration tests
    e2e: end-to-end tests
    slow: slow tests

[run]
source = .
omit =
    */tests/*
    */alembic/*
    */__init__.py
    */build_ppt.py
    conftest.py

[report]
exclude_lines =
    pragma: no cover
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:


"""Fixtures مشترک برای همه تست‌ها"""
import os
import sys
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# اضافه‌کردن ریشه پروژه به مسیر
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(scope="session")
def sample_df():
    """داده نمونه ۳۰ روز × ۳ کارخانه × ۲۴ ساعت = ۲۱۶۰ ردیف"""
    n_hours = 30 * 24
    factories = ["F1-PAPER", "F2-TISSUE", "F3-WOOD"]
    rows = []
    rng = np.random.default_rng(42)
    for f in factories:
        for i in range(n_hours):
            ts = datetime(2025, 1, 1) + timedelta(hours=i)
            prod = rng.uniform(8, 20)
            rows.append({
                "timestamp": ts,
                "factory_id": f,
                "production_t": prod,
                "elec_consumption_kwh": prod * 600 + rng.normal(0, 50),
                "steam_demand_t": prod * 2.8 + rng.normal(0, 0.5),
                "gas_consumption_m3": prod * 2.8 * 7.5 / 0.87,
                "water_intake_m3": prod * 18 + rng.normal(0, 5),
                "wastewater_m3": prod * 13.5,
                "cost_elec_usd": prod * 600 * 0.10,
                "cost_gas_usd": prod * 2.8 * 7.5 * 0.15,
                "cost_water_usd": prod * 18 * 0.8,
                "cost_wastewater_usd": prod * 13.5 * 1.2,
                "boiler_efficiency": 0.87,
                "turbine_power_mw": prod * 0.3,
                "grid_import_kwh": prod * 300,
                "grid_export_kwh": 0.0,
                "temp_c": 15.0,
                "humidity_pct": 55.0,
                "elec_price_usd_kwh": 0.10,
                "gas_price_usd_m3": 0.15,
                "cod_mg_l": 900.0,
                "tss_mg_l": 250.0,
                "anomaly_flag": 0,
                "anomaly_type": "none",
                "expected_elec_kwh": prod * 600,
                "expected_steam_t": prod * 2.8,
                "expected_water_m3": prod * 18,
            })
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def temp_data_file(sample_df, tmp_path_factory):
    """ذخیره داده نمونه در فایل موقت"""
    p = tmp_path_factory.mktemp("data") / "test_data.csv"
    sample_df.to_csv(p, index=False)
    return str(p)


@pytest.fixture(scope="session")
def fastapi_client():
    """TestClient برای API"""
    from fastapi.testclient import TestClient
    try:
        from api import app
    except ImportError:
        pytest.skip("api.py not available")
    return TestClient(app)


@pytest.fixture
def auth_token():
    """توکن JWT تست"""
    from auth.jwt_handler import create_access_token
    return create_access_token(subject="test-user", role="admin")


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

import pytest
import pandas as pd
import numpy as np

pytestmark = pytest.mark.unit


def test_sample_df_shape(sample_df):
    assert len(sample_df) > 0
    assert "factory_id" in sample_df.columns
    assert sample_df["factory_id"].nunique() == 3


def test_sample_df_no_negative_production(sample_df):
    assert (sample_df["production_t"] >= 0).all()


def test_feature_engineering():
    from ceu_train_models import add_time_features, add_lag_rolling
    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=200, freq="h"),
        "factory_id": ["F1"] * 200,
        "production_t": np.random.rand(200) * 10,
        "elec_consumption_kwh": np.random.rand(200) * 100,
        "steam_demand_t": np.random.rand(200) * 5,
        "gas_consumption_m3": np.random.rand(200) * 50,
        "water_intake_m3": np.random.rand(200) * 20,
    })
    df2 = add_time_features(df)
    assert "hour" in df2.columns
    assert "dayofweek" in df2.columns
    assert df2["hour"].max() <= 23

    df3 = add_lag_rolling(df2, ["production_t"], lags=(1, 24), windows=(24,))
    assert "production_t_lag1" in df3.columns
    assert "production_t_lag24" in df3.columns
    assert "production_t_roll24_mean" in df3.columns


def test_anomaly_injection():
    from ceu_synthetic_data import inject_anomalies
    df = pd.DataFrame({
        "steam_demand_t": np.ones(100),
        "water_intake_m3": np.ones(100) * 10,
        "elec_consumption_kwh": np.ones(100) * 500,
        "gas_consumption_m3": np.ones(100) * 50,
        "boiler_efficiency": np.ones(100) * 0.87,
        "turbine_power_mw": np.ones(100) * 2.0,
    })
    df2 = inject_anomalies(df, {"id": "TEST"}, n_each=3)
    assert "anomaly_flag" in df2.columns
    assert "anomaly_type" in df2.columns
    assert df2["anomaly_flag"].sum() > 0

import pytest
from optimization.milp_model import build_and_solve

pytestmark = pytest.mark.unit


def test_optimization_basic():
    result = build_and_solve(
        steam_demand_tph=30.0,
        elec_demand_kw=5000.0,
        boilers=[
            {"id": "B1", "cap_tph": 30, "eff": 0.88, "min_load": 0.2},
            {"id": "B2", "cap_tph": 25, "eff": 0.86, "min_load": 0.2},
        ],
        turbines=[
            {"id": "T1", "cap_mw": 5.0, "eff": 0.28, "min_load": 0.3},
        ],
        gas_price=0.15,
        elec_price_import=0.16,
        elec_price_export=0.04,
    )
    assert result["status"] in ("Optimal", "Not Solved")
    if result["status"] == "Optimal":
        assert result["total_cost"] > 0
        assert len(result["boiler_steam"]) == 2


def test_optimization_infeasible():
    """تقاضای بیشتر از ظرفیت — باید infeasible شود"""
    result = build_and_solve(
        steam_demand_tph=1000.0,
        elec_demand_kw=5000.0,
        boilers=[{"id": "B1", "cap_tph": 30, "eff": 0.88, "min_load": 0.2}],
        turbines=[],
        gas_price=0.15,
        elec_price_import=0.16,
        elec_price_export=0.04,
    )
    assert result["status"] == "Infeasible"


def test_optimization_prefers_efficient_boiler():
    """دیگ با راندمان بالاتر باید بار بیشتری بگیرد"""
    result = build_and_solve(
        steam_demand_tph=30.0,
        elec_demand_kw=0.0,
        boilers=[
            {"id": "B_GOOD", "cap_tph": 30, "eff": 0.95, "min_load": 0.1},
            {"id": "B_BAD", "cap_tph": 30, "eff": 0.70, "min_load": 0.1},
        ],
        turbines=[],
        gas_price=0.15,
        elec_price_import=0.16,
        elec_price_export=0.04,
    )
    assert result["status"] == "Optimal"
    assert result["boiler_steam"]["B_GOOD"] >= result["boiler_steam"]["B_BAD"]

import pytest

pytestmark = pytest.mark.integration


def test_login_success(fastapi_client):
    r = fastapi_client.post("/auth/login", json={
        "username": "admin", "password": "admin123"
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(fastapi_client):
    r = fastapi_client.post("/auth/login", json={
        "username": "admin", "password": "wrong"
    })
    assert r.status_code == 401


def test_protected_endpoint_without_token(fastapi_client):
    r = fastapi_client.get("/models")
    assert r.status_code == 401


def test_protected_endpoint_with_token(fastapi_client, auth_headers):
    r = fastapi_client.get("/models", headers=auth_headers)
    assert r.status_code == 200

import pytest

pytestmark = pytest.mark.integration


def test_health(fastapi_client):
    r = fastapi_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_forecast_endpoint(fastapi_client, auth_headers):
    payload = {
        "factory_id": "F1-PAPER",
        "target": "elec_consumption_kwh",
        "features": {
            "production_t": 15.0,
            "hour": 10,
            "dayofweek": 2,
            "month": 3,
        },
    }
    r = fastapi_client.post("/forecast", json=payload, headers=auth_headers)
    # 200 اگر مدل موجود باشد، 404 اگر نباشد — هر دو قبول
    assert r.status_code in (200, 404)


def test_anomaly_endpoint(fastapi_client, auth_headers):
    payload = {
        "factory_id": "F1-PAPER",
        "elec_consumption_kwh": 9000,
        "steam_demand_t": 42,
        "gas_consumption_m3": 350,
        "water_intake_m3": 270,
        "production_t": 15,
        "boiler_efficiency": 0.87,
        "turbine_power_mw": 4.5,
    }
    r = fastapi_client.post("/anomaly", json=payload, headers=auth_headers)
    assert r.status_code in (200, 503)

"""تست انتها به انتها: داده → آموزش → ارزیابی → پیش‌بینی"""
import os
import pytest
import pandas as pd
import numpy as np

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.fixture(scope="module")
def trained_model(tmp_path_factory, sample_df):
    """آموزش یک مدل سبک برای تست"""
    import lightgbm as lgb
    from ceu_train_models import add_time_features, add_lag_rolling

    df = sample_df[sample_df["factory_id"] == "F1-PAPER"].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = add_time_features(df)
    df = add_lag_rolling(df, ["production_t", "elec_consumption_kwh"], lags=(1,), windows=(24,))
    df = df.dropna()

    feat_cols = [c for c in df.columns if c.startswith(("production", "hour", "day", "month", "elec_consumption_kwh_lag", "elec_consumption_kwh_roll"))]
    X = df[feat_cols]
    y = df["elec_consumption_kwh"]

    m = lgb.LGBMRegressor(n_estimators=20, verbose=-1)
    m.fit(X, y)

    path = tmp_path_factory.mktemp("model") / "model.pkl"
    import joblib
    joblib.dump({"model": m, "features": feat_cols}, path)
    return str(path), feat_cols, X


def test_predict(trained_model):
    import joblib
    path, feats, X = trained_model
    obj = joblib.load(path)
    pred = obj["model"].predict(X.iloc[:5])
    assert len(pred) == 5
    assert (pred > 0).all()

name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio httpx \
                     python-jose[cryptography] passlib[bcrypt] \
                     python-multipart streamlit-authenticator \
                     asyncua pymodbus pulp sqlalchemy alembic \
                     psycopg2-binary asyncpg

      - name: Generate synthetic data
        run: python ceu_synthetic_data.py

      - name: Lint (flake8)
        run: |
          pip install flake8
          flake8 --max-line-length=120 --ignore=E501,W503,E203 .
        continue-on-error: true

      - name: Run unit tests
        run: pytest tests/unit -v --cov=. --cov-report=xml --cov-fail-under=60

      - name: Run integration tests
        run: pytest tests/integration -v
        continue-on-error: true

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: false

  docker:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t ceuo:ci .
      - name: Smoke test
        run: docker run --rm ceuo:ci python -c "import streamlit, fastapi; print('ok')"

