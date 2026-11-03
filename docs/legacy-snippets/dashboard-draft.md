# داشبورد حرفه‌ای + سرویس API برای CEUO

ساختار کامل شامل: **داشبورد Streamlit چندصفحه‌ای** + **FastAPI برای inference** + **اجرای Docker**.

```
ceu_project/
├── app.py                ← داشبورد Streamlit
├── api.py                ← FastAPI (inference)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .streamlit/
    └── config.toml       ← تم و تنظیمات
```

---

## 1) `requirements.txt` (به‌روزرسانی‌شده)

```txt
numpy>=1.24
pandas>=2.0
lightgbm>=4.0
scikit-learn>=1.3
joblib>=1.3
plotly>=5.18
streamlit>=1.31
fastapi>=0.109
uvicorn[standard]>=0.27
pydantic>=2.5
pyarrow>=14.0
mlflow>=2.9
```

---

## 2) `.streamlit/config.toml` — تم حرفه‌ای

```toml
[theme]
primaryColor          = "#2563EB"
backgroundColor       = "#0F172A"
secondaryBackgroundColor = "#1E293B"
textColor             = "#E2E8F0"
font                  = "sans serif"

[server]
headless = true
port = 8501

[browser]
gatherUsageStats = false
```

---

## 3) `app.py` — داشبورد اصلی

```python
"""
CEUO Dashboard — داشبورد حرفه‌ای سامانه هوشمند بهینه‌سازی انرژی
اجرا:  streamlit run app.py
"""

import os
import json
import warnings
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="CEUO — داشبورد انرژی",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA       = "ceuo_data.csv"
METRICS_J  = "metrics.json"
MODEL_DIR  = "models"
TARGETS    = ["elec_consumption_kwh", "steam_demand_t",
              "gas_consumption_m3", "water_intake_m3"]

TARGET_FA = {
    "elec_consumption_kwh": "برق (kWh)",
    "steam_demand_t":       "بخار (ton)",
    "gas_consumption_m3":   "گاز (m³)",
    "water_intake_m3":      "آب (m³)",
}

FACTORY_FA = {
    "F1-PAPER":  "کاغذ",
    "F2-TISSUE": "تیشو",
    "F3-WOOD":   "چوب / MDF",
}

PALETTE = {
    "elec":   "#3B82F6",
    "steam":  "#F59E0B",
    "gas":    "#EF4444",
    "water":  "#06B6D4",
    "ok":     "#10B981",
    "warn":   "#F59E0B",
    "danger": "#EF4444",
    "muted":  "#64748B",
}


# ---------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------
st.markdown("""
<style>
  /* KPI cards */
  .kpi-card {
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 18px 22px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.25);
    transition: transform .15s ease, border-color .15s ease;
  }
  .kpi-card:hover {
    transform: translateY(-2px);
    border-color: #3B82F6;
  }
  .kpi-label {
    color: #94A3B8;
    font-size: 13px;
    font-weight: 500;
    margin-bottom: 6px;
    letter-spacing: .3px;
  }
  .kpi-value {
    color: #F1F5F9;
    font-size: 26px;
    font-weight: 700;
    line-height: 1.1;
  }
  .kpi-delta {
    font-size: 13px;
    margin-top: 6px;
    font-weight: 600;
  }
  .kpi-delta.up   { color: #10B981; }
  .kpi-delta.down { color: #EF4444; }
  .kpi-unit { font-size: 14px; color: #94A3B8; font-weight: 400; }

  /* Section headers */
  .section-title {
    font-size: 20px;
    font-weight: 700;
    color: #E2E8F0;
    margin: 8px 0 14px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #334155;
  }

  /* Status badges */
  .badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
  }
  .badge-ok    { background: rgba(16,185,129,.15); color:#10B981; }
  .badge-warn  { background: rgba(245,158,11,.15); color:#F59E0B; }
  .badge-danger{ background: rgba(239,68,68,.15);  color:#EF4444; }
  .badge-info  { background: rgba(59,130,246,.15); color:#3B82F6; }

  /* Hide Streamlit default footer */
  footer { visibility: hidden; }
  #MainMenu { visibility: hidden; }

  /* Tabs */
  .stTabs [data-baseweb="tab-list"] { gap: 6px; }
  .stTabs [data-baseweb="tab"] {
    background-color: #1E293B;
    border-radius: 8px 8px 0 0;
    padding: 8px 16px;
  }
  .stTabs [aria-selected="true"] {
    background-color: #2563EB;
    color: white;
  }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data():
    if not os.path.exists(DATA):
        return None
    df = pd.read_csv(DATA, parse_dates=["timestamp"])
    df = df.sort_values(["factory_id", "timestamp"]).reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False)
def load_metrics():
    if not os.path.exists(METRICS_J):
        return None
    with open(METRICS_J, encoding="utf-8") as f:
        return json.load(f)


@st.cache_resource(show_spinner=False)
def load_model(factory_id, target):
    path = os.path.join(MODEL_DIR, f"lgb__{factory_id}__{target}.pkl")
    if not os.path.exists(path):
        return None
    return joblib.load(path)


# ---------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------
def kpi_card(label, value, unit="", delta=None, delta_label="", invert=False):
    """کارت KPI با دلتا"""
    delta_html = ""
    if delta is not None:
        good = (delta >= 0) if invert else (delta <= 0)
        cls = "up" if good else "down"
        arrow = "▲" if delta >= 0 else "▼"
        delta_html = (
            f'<div class="kpi-delta {cls}">{arrow} {abs(delta):.1f}% '
            f'<span style="color:#64748B;font-weight:400;">{delta_label}</span></div>'
        )
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value} <span class="kpi-unit">{unit}</span></div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def section(title):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def badge(text, kind="info"):
    return f'<span class="badge badge-{kind}">{text}</span>'


def fmt_num(x, dec=1):
    try:
        return f"{x:,.{dec}f}"
    except Exception:
        return "—"


def period_delta(df, col, days):
    """مقایسه بازه اخیر با بازه قبل از آن"""
    end = df["timestamp"].max()
    recent = df[df["timestamp"] > end - timedelta(days=days)][col].sum()
    prev   = df[(df["timestamp"] > end - timedelta(days=2*days)) &
                (df["timestamp"] <= end - timedelta(days=days))][col].sum()
    if prev == 0:
        return 0.0
    return (recent - prev) / prev * 100


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------
def sidebar(df):
    st.sidebar.markdown("""
    <div style="text-align:center;padding:10px 0 20px 0;">
      <div style="font-size:28px;">⚡</div>
      <div style="font-size:18px;font-weight:700;color:#F1F5F9;">CEUO</div>
      <div style="font-size:12px;color:#94A3B8;">سامانه هوشمند بهینه‌سازی انرژی</div>
    </div>
    """, unsafe_allow_html=True)

    page = st.sidebar.radio(" ", [
        "🏠 نمای کلی",
        "📊 شاخص‌ها و مقایسه",
        "🔮 پیش‌بینی مصرف",
        "🚨 تشخیص انحراف",
        "⚙️ بهینه‌سازی بخار/برق",
        "🌊 آب و پساب",
        "💰 هزینه و صرفه‌جویی",
        "📄 گزارش‌ها",
    ], label_visibility="collapsed")

    st.sidebar.markdown("---")

    factories = sorted(df["factory_id"].unique())
    selected_f = st.sidebar.multiselect(
        "کارخانه", factories,
        default=factories,
        format_func=lambda x: f"{x} — {FACTORY_FA.get(x, '')}",
    )

    end = df["timestamp"].max()
    start_default = end - timedelta(days=30)
    date_range = st.sidebar.date_input(
        "بازه زمانی",
        value=(start_default.date(), end.date()),
        min_value=df["timestamp"].min().date(),
        max_value=end.date(),
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("نسخه 1.0.0 — Petropalatus")
    return page, selected_f, date_range


# ---------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------
def apply_filters(df, factories, date_range):
    if not factories:
        factories = sorted(df["factory_id"].unique())
    if len(date_range) == 2:
        d0, d1 = date_range
        mask = (df["timestamp"].dt.date >= d0) & (df["timestamp"].dt.date <= d1)
        df = df[mask]
    return df[df["factory_id"].isin(factories)].copy()


# ---------------------------------------------------------------------
# PAGE: Overview
# ---------------------------------------------------------------------
def page_overview(df):
    section("خلاصه وضعیت")

    total_cost = df[["cost_elec_usd", "cost_gas_usd",
                     "cost_water_usd", "cost_wastewater_usd"]].sum().sum()
    prod_total = df["production_t"].sum()
    n_anomaly  = int(df["anomaly_flag"].sum())
    sec_elec   = df["elec_consumption_kwh"].sum() / max(prod_total, 1)

    cols = st.columns(5)
    with cols[0]:
        kpi_card("هزینه انرژی کل", fmt_num(total_cost, 0), "$",
                 period_delta(df, "cost_elec_usd", 7), "نسبت به ۷ روز قبل", invert=True)
    with cols[1]:
        kpi_card("تولید کل", fmt_num(prod_total, 0), "ton",
                 period_delta(df, "production_t", 7), "نسبت به ۷ روز قبل")
    with cols[2]:
        kpi_card("شاخص ویژه برق", fmt_num(sec_elec, 0), "kWh/ton")
    with cols[3]:
        kpi_card("مصرف بخار", fmt_num(df["steam_demand_t"].sum(), 0), "ton")
    with cols[4]:
        kpi_card("رخداد انحراف", f"{n_anomaly}", "مورد",
                 delta=None)

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # --- trend chart (dual axis) ---
    section("روند هزینه و تولید")
    daily = (df.set_index("timestamp")
               .resample("D")
               .agg({"production_t": "sum",
                     "cost_elec_usd": "sum",
                     "cost_gas_usd": "sum",
                     "cost_water_usd": "sum",
                     "cost_wastewater_usd": "sum"})
               .reset_index())
    daily["cost_total"] = daily[["cost_elec_usd", "cost_gas_usd",
                                 "cost_water_usd", "cost_wastewater_usd"]].sum(axis=1)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=daily["timestamp"], y=daily["production_t"],
                         name="تولید (ton)", marker_color=PALETTE["elec"],
                         opacity=0.75),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=daily["timestamp"], y=daily["cost_total"],
                             name="هزینه ($)", line=dict(color=PALETTE["warn"], width=2.5),
                             mode="lines"),
                  secondary_y=True)
    fig.update_layout(
        height=340, template="plotly_dark", hovermode="x unified",
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.1),
    )
    fig.update_yaxes(title_text="تولید (ton)", secondary_y=False)
    fig.update_yaxes(title_text="هزینه ($)", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    # --- breakdown by factory ---
    col1, col2 = st.columns(2)
    with col1:
        section("سهم هزینه به تفکیک کارخانه")
        bd = df.groupby("factory_id").agg({
            "cost_elec_usd": "sum", "cost_gas_usd": "sum",
            "cost_water_usd": "sum", "cost_wastewater_usd": "sum"
        }).reset_index()
        bd["total"] = bd.iloc[:, 1:].sum(axis=1)
        fig = px.pie(bd, names="factory_id", values="total", hole=0.55,
                     color_discrete_sequence=px.colors.sequential.Blues_r)
        fig.update_layout(height=320, template="plotly_dark",
                          paper_bgcolor="rgba(0,0,0,0)",
                          margin=dict(l=10, r=10, t=10, b=10))
        fig.update_traces(textinfo="label+percent")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        section("ترکیب هزینه‌ها")
        parts = {
            "برق":  df["cost_elec_usd"].sum(),
            "گاز":  df["cost_gas_usd"].sum(),
            "آب":   df["cost_water_usd"].sum(),
            "پساب": df["cost_wastewater_usd"].sum(),
        }
        fig = go.Figure(go.Bar(
            x=list(parts.keys()), y=list(parts.values()),
            marker_color=[PALETTE["elec"], PALETTE["gas"],
                          PALETTE["water"], PALETTE["steam"]],
            text=[f"${v:,.0f}" for v in parts.values()],
            textposition="outside",
        ))
        fig.update_layout(height=320, template="plotly_dark",
                          paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)",
                          margin=dict(l=10, r=10, t=30, b=10),
                          showlegend=False,
                          yaxis_title="هزینه ($)")
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------
# PAGE: KPIs & comparison
# ---------------------------------------------------------------------
def page_kpis(df):
    section("شاخص‌های ویژه انرژی")

    # calc per factory
    agg = df.groupby("factory_id").agg({
        "production_t": "sum",
        "elec_consumption_kwh": "sum",
        "steam_demand_t": "sum",
        "gas_consumption_m3": "sum",
        "water_intake_m3": "sum",
    }).reset_index()
    agg["kwh_per_ton"]    = agg["elec_consumption_kwh"] / agg["production_t"].clip(lower=1)
    agg["steam_per_ton"]  = agg["steam_demand_t"]       / agg["production_t"].clip(lower=1)
    agg["gas_per_ton"]    = agg["gas_consumption_m3"]   / agg["production_t"].clip(lower=1)
    agg["water_per_ton"]  = agg["water_intake_m3"]      / agg["production_t"].clip(lower=1)

    # chart
    fig = make_subplots(rows=2, cols=2,
                        subplot_titles=("kWh/ton", "بخار/ton", "گاز/ton", "آب/ton"))
    for i, (metric, color) in enumerate([
        ("kwh_per_ton", PALETTE["elec"]),
        ("steam_per_ton", PALETTE["steam"]),
        ("gas_per_ton", PALETTE["gas"]),
        ("water_per_ton", PALETTE["water"]),
    ]):
        r, c = divmod(i, 2)
        fig.add_trace(go.Bar(x=agg["factory_id"], y=agg[metric],
                             marker_color=color, showlegend=False,
                             text=[f"{v:.0f}" for v in agg[metric]],
                             textposition="outside"),
                      row=r+1, col=c+1)
    fig.update_layout(height=480, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # comparison table
    section("جدول مقایسه‌ای کارخانه‌ها")
    disp = agg.copy()
    disp.columns = ["کارخانه", "تولید (ton)", "برق (kWh)", "بخار (ton)",
                    "گاز (m³)", "آب (m³)", "kWh/ton", "بخار/ton", "گاز/ton", "آب/ton"]
    st.dataframe(
        disp.style.format({c: "{:,.1f}" for c in disp.columns if c not in ("کارخانه",)}),
        use_container_width=True, hide_index=True,
    )


# ---------------------------------------------------------------------
# PAGE: Forecast
# ---------------------------------------------------------------------
def page_forecast(df):
    section("پیش‌بینی مصرف با مدل LightGBM")

    col1, col2 = st.columns(2)
    with col1:
        factory = st.selectbox("کارخانه", sorted(df["factory_id"].unique()),
                               format_func=lambda x: f"{x} — {FACTORY_FA.get(x,'')}")
    with col2:
        target = st.selectbox("هدف", TARGETS, format_func=lambda x: TARGET_FA[x])

    obj = load_model(factory, target)
    fdf = df[df["factory_id"] == factory].copy()

    if obj is None:
        st.warning("مدل یافت نشد — ابتدا `python ceu_train_models.py` را اجرا کنید.")
        return

    model, feat_cols = obj["model"], obj["features"]

    # feature engineering همان قبیل آموزش
    try:
        from ceu_train_models import build_features
        fdf = build_features(fdf)
    except Exception:
        st.error("خطا در بارگذاری توابع feature engineering")
        return

    # آخرین ۳۰ روز
    end = fdf["timestamp"].max()
    recent = fdf[fdf["timestamp"] > end - timedelta(days=30)].dropna(subset=feat_cols)
    if len(recent) == 0:
        st.warning("داده کافی برای این بازه وجود ندارد.")
        return

    y_pred = model.predict(recent[feat_cols])
    y_true = recent[target].values

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=recent["timestamp"], y=y_true,
                             name="واقعی", line=dict(color=PALETTE["muted"], width=2)))
    fig.add_trace(go.Scatter(x=recent["timestamp"], y=y_pred,
                             name="پیش‌بینی", line=dict(color=PALETTE["elec"], width=2, dash="dot")))
    fig.update_layout(height=380, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      hovermode="x unified",
                      margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # metric cards
    from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
    mae  = mean_absolute_error(y_true, y_pred)
    mape = mean_absolute_percentage_error(y_true, y_pred) * 100
    r2   = r2_score(y_true, y_pred)

    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("MAE", fmt_num(mae, 1), TARGET_FA[target].split("(")[-1].rstrip(")"))
    with c2: kpi_card("MAPE", fmt_num(mape, 2), "%")
    with c3: kpi_card("R²", fmt_num(r2, 3), "")

    # download
    out = pd.DataFrame({
        "timestamp": recent["timestamp"].values,
        "actual":    y_true,
        "predicted": y_pred,
        "residual":  y_true - y_pred,
    })
    st.download_button(
        "📥 دانلود پیش‌بینی (CSV)",
        out.to_csv(index=False).encode("utf-8"),
        file_name=f"forecast_{factory}_{target}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------
# PAGE: Anomaly
# ---------------------------------------------------------------------
def page_anomaly(df):
    section("رخدادهای انحراف")

    # آمار
    anom = df[df["anomaly_flag"] == 1]
    if len(anom) == 0:
        st.info("رخداد انحرافی در بازه انتخابی وجود ندارد.")
        return

    counts = anom["anomaly_type"].value_counts().reset_index()
    counts.columns = ["نوع", "تعداد"]

    col1, col2 = st.columns([1, 1])
    with col1:
        fig = px.bar(counts, x="تعداد", y="نوع", orientation="h",
                     color="تعداد",
                     color_continuous_scale=["#1E3A8A", "#EF4444"])
        fig.update_layout(height=320, template="plotly_dark",
                          paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)",
                          margin=dict(l=10, r=10, t=20, b=10),
                          showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        by_fac = anom.groupby("factory_id").size().reset_index(name="count")
        fig = px.pie(by_fac, names="factory_id", values="count", hole=0.5,
                     color_discrete_sequence=px.colors.sequential.Reds_r)
        fig.update_layout(height=320, template="plotly_dark",
                          paper_bgcolor="rgba(0,0,0,0)",
                          margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # timeline
    section("خط زمانی رخدادها")
    fig = go.Figure()
    colors = {"boiler_fouling": "#EF4444", "steam_leak": "#F59E0B",
              "water_leak": "#06B6D4", "turbine_efficiency_drop": "#8B5CF6",
              "motor_overload": "#EC4899", "sensor_spike": "#64748B"}
    for t, grp in anom.groupby("anomaly_type"):
        fig.add_trace(go.Scatter(
            x=grp["timestamp"], y=[t]*len(grp),
            mode="markers", name=t,
            marker=dict(size=8, color=colors.get(t, "#64748B")),
        ))
    fig.update_layout(height=300, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=20, b=10),
                      xaxis_title="زمان", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

    # table
    section("جدول رخدادها")
    table = anom[["timestamp", "factory_id", "anomaly_type",
                  "elec_consumption_kwh", "steam_demand_t",
                  "water_intake_m3", "production_t"]].copy()
    table.columns = ["زمان", "کارخانه", "نوع", "برق", "بخار", "آب", "تولید"]
    st.dataframe(table.head(200), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------
# PAGE: Optimization
# ---------------------------------------------------------------------
def page_optimization(df):
    section("بهینه‌سازی بهره‌برداری دیگ‌ها و توربین‌ها")

    m = load_metrics()
    if m and "forecast" in m:
        c1, c2, c3 = st.columns(3)
        avg_mape = np.mean([v["MAPE"] for v in m["forecast"].values()])
        cost = m.get("cost", {})
        with c1: kpi_card("میانگین MAPE مدل‌ها", fmt_num(avg_mape, 2), "%")
        with c2: kpi_card("هزینه پایه (test)", fmt_num(cost.get("baseline_cost_usd", 0), 0), "$")
        with c3: kpi_card("صرفه‌جویی برآوردی",
                          fmt_num(cost.get("estimated_savings_usd", 0), 0), "$",
                          delta=cost.get("savings_rate_pct", 0), "درصد بهبود")

    st.markdown("---")
    section("تنظیمات سناریو")

    c1, c2 = st.columns(2)
    with c1:
        production_factor = st.slider("ضریب تولید", 0.5, 1.2, 1.0, 0.05)
        gas_price = st.number_input("قیمت گاز ($/m³)", value=0.15, step=0.01, format="%.3f")
    with c2:
        elec_peak = st.number_input("قیمت برق پیک ($/kWh)", value=0.16, step=0.01, format="%.3f")
        elec_off  = st.number_input("قیمت برق غیرپیک ($/kWh)", value=0.06, step=0.01, format="%.3f")

    if st.button("🚀 اجرای بهینه‌سازی", type="primary"):
        with st.spinner("در حال حل مدل…"):
            # شبیه‌سازی بهینه‌سازی (در محصول واقعی MILP اجرا می‌شود)
            recent = df[df["timestamp"] > df["timestamp"].max() - timedelta(days=7)]
            base_steam = recent["steam_demand_t"].mean()
            base_gas   = recent["gas_consumption_m3"].mean()
            base_elec  = recent["elec_consumption_kwh"].mean()

            opt_steam = base_steam * production_factor
            opt_gas   = base_gas   * production_factor * 0.95    # بهبود ۵٪
            opt_elec  = base_elec  * production_factor * 0.97    # بهبود ۳٪

            baseline_cost = base_gas * gas_price + base_elec * elec_peak
            opt_cost      = opt_gas * gas_price + opt_elec * elec_peak
            savings       = baseline_cost - opt_cost
            savings_pct   = savings / baseline_cost * 100 if baseline_cost else 0

            c1, c2, c3, c4 = st.columns(4)
            with c1: kpi_card("گاز مصرفی", fmt_num(opt_gas, 0), "m³",
                              delta=(opt_gas - base_gas) / base_gas * 100 if base_gas else 0,
                              delta_label="نسبت به پایه", invert=True)
            with c2: kpi_card("برق مصرفی", fmt_num(opt_elec, 0), "kWh",
                              delta=(opt_elec - base_elec) / base_elec * 100 if base_elec else 0,
                              delta_label="نسبت به پایه", invert=True)
            with c3: kpi_card("بخار تولیدی", fmt_num(opt_steam, 0), "ton")
            with c4: kpi_card("صرفه‌جویی روزانه", fmt_num(savings, 0), "$/day",
                              delta=savings_pct, "درصد", invert=False)

            # chart مقایسه
            fig = go.Figure()
            cats = ["گاز", "برق"]
            base_vals = [base_gas, base_elec]
            opt_vals  = [opt_gas, opt_elec]
            fig.add_trace(go.Bar(name="پایه", x=cats, y=base_vals,
                                 marker_color=PALETTE["muted"],
                                 text=[fmt_num(v, 0) for v in base_vals],
                                 textposition="outside"))
            fig.add_trace(go.Bar(name="بهینه", x=cats, y=opt_vals,
                                 marker_color=PALETTE["ok"],
                                 text=[fmt_num(v, 0) for v in opt_vals],
                                 textposition="outside"))
            fig.update_layout(height=340, template="plotly_dark", barmode="group",
                              paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)",
                              margin=dict(l=10, r=10, t=30, b=10),
                              legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, use_container_width=True)

            st.success(f"✅ بهینه‌سازی انجام شد — صرفه‌جویی برآوردی: **${savings:,.0f} در روز** ({savings_pct:.1f}%)")
    else:
        st.info("پارامترها را تنظیم و دکمه اجرا را بزنید.")


# ---------------------------------------------------------------------
# PAGE: Water & Wastewater
# ---------------------------------------------------------------------
def page_water(df):
    section("پایش آب و پساب")

    agg = df.groupby("factory_id").agg({
        "water_intake_m3": "sum",
        "wastewater_m3": "sum",
        "cod_mg_l": "mean",
        "tss_mg_l": "mean",
        "production_t": "sum",
    }).reset_index()
    agg["water_per_ton"] = agg["water_intake_m3"] / agg["production_t"].clip(lower=1)
    agg["recovery_pct"]  = (agg["production_t"] * 0 - agg["wastewater_m3"] +
                            agg["water_intake_m3"]) / agg["water_intake_m3"].clip(lower=1) * 100
    agg["recovery_pct"]  = agg["recovery_pct"].clip(0, 100)

    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("کل آب ورودی", fmt_num(df["water_intake_m3"].sum(), 0), "m³")
    with c2: kpi_card("کل پساب", fmt_num(df["wastewater_m3"].sum(), 0), "m³")
    with c3: kpi_card("COD میانگین", fmt_num(df["cod_mg_l"].mean(), 0), "mg/L")

    st.markdown("---")
    section("روند روزانه")
    daily = (df.set_index("timestamp").resample("D")
               .agg({"water_intake_m3": "sum",
                     "wastewater_m3": "sum"})
               .reset_index())
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["timestamp"], y=daily["water_intake_m3"],
                             name="آب ورودی", line=dict(color=PALETTE["water"], width=2.5)))
    fig.add_trace(go.Scatter(x=daily["timestamp"], y=daily["wastewater_m3"],
                             name="پساب", line=dict(color=PALETTE["warn"], width=2.5),
                             fill="tozeroy", fillcolor="rgba(245,158,11,0.1)"))
    fig.update_layout(height=340, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      hovermode="x unified",
                      margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    section("جدول تفکیکی کارخانه‌ها")
    disp = agg[["factory_id", "water_per_ton", "recovery_pct",
                "cod_mg_l", "tss_mg_l"]].copy()
    disp.columns = ["کارخانه", "آب/ton", "بازچرخانی %", "COD", "TSS"]
    st.dataframe(disp.style.format({"آب/ton": "{:.1f}", "بازچرخانی %": "{:.1f}",
                                     "COD": "{:.0f}", "TSS": "{:.0f}"}),
                 use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------
# PAGE: Cost
# ---------------------------------------------------------------------
def page_cost(df):
    section("تحلیل هزینه و صرفه‌جویی")

    m = load_metrics()
    cost = m.get("cost", {}) if m else {}

    total = df[["cost_elec_usd", "cost_gas_usd",
                "cost_water_usd", "cost_wastewater_usd"]].sum().sum()

    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("هزینه کل", fmt_num(total, 0), "$")
    with c2: kpi_card("صرفه‌جویی برآوردی", fmt_num(cost.get("estimated_savings_usd", 0), 0), "$")
    with c3: kpi_card("نرخ صرفه‌جویی", fmt_num(cost.get("savings_rate_pct", 0), 2), "%")

    st.markdown("---")
    section("روند روزانه هزینه")
    daily = (df.set_index("timestamp").resample("D")
               .agg({"cost_elec_usd": "sum", "cost_gas_usd": "sum",
                     "cost_water_usd": "sum", "cost_wastewater_usd": "sum"})
               .reset_index())
    fig = go.Figure()
    for col, name, color in [
        ("cost_elec_usd", "برق", PALETTE["elec"]),
        ("cost_gas_usd", "گاز", PALETTE["gas"]),
        ("cost_water_usd", "آب", PALETTE["water"]),
        ("cost_wastewater_usd", "پساب", PALETTE["steam"]),
    ]:
        fig.add_trace(go.Scatter(x=daily["timestamp"], y=daily[col],
                                 stackgroup="one", name=name,
                                 line=dict(color=color, width=1)))
    fig.update_layout(height=380, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      hovermode="x unified",
                      margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------
# PAGE: Reports
# ---------------------------------------------------------------------
def page_reports(df):
    section("گزارش‌ها و خروجی‌ها")

    m = load_metrics()
    if m:
        with st.expander("📊 خلاصه متریک‌های مدل", expanded=True):
            fc = m.get("forecast", {})
            if fc:
                rows = []
                for k, v in fc.items():
                    fid, tgt = k.split("__")
                    rows.append({
                        "کارخانه": fid,
                        "هدف": TARGET_FA.get(tgt, tgt),
                        "N": v["n"],
                        "MAE": f"{v['MAE']:,.1f}",
                        "MAPE %": f"{v['MAPE']:.2f}",
                        "R²": f"{v['R2']:.3f}",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            an = m.get("anomaly", {})
            if an:
                st.markdown("**تشخیص انحراف**")
                c1, c2, c3, c4 = st.columns(4)
                with c1: kpi_card("F1", f"{an.get('F1', 0):.3f}", "")
                with c2: kpi_card("Precision", f"{an.get('Precision', 0):.3f}", "")
                with c3: kpi_card("Recall", f"{an.get('Recall', 0):.3f}", "")
                with c4: kpi_card("AUC-ROC", f"{an.get('AUC_ROC', 0):.3f}", "")

    st.markdown("---")
    section("خروجی CSV")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "📥 داده فیلترشده",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"ceuo_filtered_{datetime.now():%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with c2:
        if os.path.exists(METRICS_J):
            with open(METRICS_J, "rb") as f:
                st.download_button(
                    "📥 متریک‌های مدل (JSON)",
                    f.read(),
                    file_name="metrics.json",
                    mime="application/json",
                    use_container_width=True,
                )
    with c3:
        if os.path.exists("model_evaluation_report.md"):
            with open("model_evaluation_report.md", "rb") as f:
                st.download_button(
                    "📥 گزارش ارزیابی (MD)",
                    f.read(),
                    file_name="model_evaluation_report.md",
                    mime="text/markdown",
                    use_container_width=True,
                )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main():
    df = load_data()
    if df is None:
        st.error(f"فایل `{DATA}` پیدا نشد. ابتدا `python ceu_synthetic_data.py` را اجرا کنید.")
        st.stop()

    page, factories, date_range = sidebar(df)
    df = apply_filters(df, factories, date_range)

    if df.empty:
        st.warning("داده‌ای با فیلتر انتخابی وجود ندارد.")
        st.stop()

    # header
    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                margin-bottom:10px;">
      <div>
        <div style="font-size:24px;font-weight:700;color:#F1F5F9;">
          داشبورد CEUO — {page.split(' ',1)[-1]}
        </div>
        <div style="color:#64748B;font-size:13px;margin-top:2px;">
          {df['timestamp'].min():%Y-%m-%d} → {df['timestamp'].max():%Y-%m-%d}
          &nbsp;·&nbsp; {len(df):,} رکورد
          &nbsp;·&nbsp; {len(factories)} کارخانه
        </div>
      </div>
      <div>{badge('Online', 'ok')}</div>
    </div>
    """, unsafe_allow_html=True)

    # route
    routes = {
        "🏠 نمای کلی":            page_overview,
        "📊 شاخص‌ها و مقایسه":     page_kpis,
        "🔮 پیش‌بینی مصرف":        page_forecast,
        "🚨 تشخیص انحراف":        page_anomaly,
        "⚙️ بهینه‌سازی بخار/برق":  page_optimization,
        "🌊 آب و پساب":           page_water,
        "💰 هزینه و صرفه‌جویی":   page_cost,
        "📄 گزارش‌ها":            page_reports,
    }
    routes[page](df)


if __name__ == "__main__":
    main()
```

---

## 4) `api.py` — FastAPI برای inference آنلاین

```python
"""
CEUO Inference API
اجرا:  uvicorn api:app --host 0.0.0.0 --port 8000
Docs:  http://localhost:8000/docs
"""

import os
import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List

app = FastAPI(
    title="CEUO Inference API",
    description="سرویس پیش‌بینی و تشخیص آنومالی سامانه CEUO",
    version="1.0.0",
)

MODEL_DIR = "models"
TARGETS   = ["elec_consumption_kwh", "steam_demand_t",
             "gas_consumption_m3", "water_intake_m3"]


# ---------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------
class ForecastRequest(BaseModel):
    factory_id: str = Field(..., examples=["F1-PAPER"])
    target:     str = Field(..., examples=["elec_consumption_kwh"])
    features:   dict = Field(..., description="دیکشنری فیچرها (مطابق training)")


class ForecastResponse(BaseModel):
    prediction: float
    target:     str
    factory_id: str


class AnomalyRequest(BaseModel):
    factory_id: str
    elec_consumption_kwh: float
    steam_demand_t:       float
    gas_consumption_m3:   float
    water_intake_m3:      float
    production_t:         float
    boiler_efficiency:    float = 0.85
    turbine_power_mw:     float = 0.0


class AnomalyResponse(BaseModel):
    is_anomaly: bool
    score:      float
    threshold:  float


# ---------------------------------------------------------------------
# Startup: load models
# ---------------------------------------------------------------------
@app.on_event("startup")
def load_all():
    app.state.models = {}
    for f in os.listdir(MODEL_DIR) if os.path.exists(MODEL_DIR) else []:
        if f.startswith("lgb__") and f.endswith(".pkl"):
            _, fid, tgt = f.replace(".pkl", "").split("__", 2)
            app.state.models[(fid, tgt)] = joblib.load(os.path.join(MODEL_DIR, f))

    iso_path = os.path.join(MODEL_DIR, "isolation_forest.pkl")
    app.state.iso = joblib.load(iso_path) if os.path.exists(iso_path) else None

    # threshold از metrics.json
    app.state.threshold = 0.0
    if os.path.exists("metrics.json"):
        import json
        with open("metrics.json", encoding="utf-8") as f:
            m = json.load(f)
            app.state.threshold = m.get("anomaly", {}).get("threshold", 0.0)

    print(f"✓ loaded {len(app.state.models)} forecast models, "
          f"iso={'yes' if app.state.iso else 'no'}")


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok",
            "models": len(app.state.models),
            "iso_loaded": app.state.iso is not None}


@app.post("/forecast", response_model=ForecastResponse)
def forecast(req: ForecastRequest):
    key = (req.factory_id, req.target)
    if key not in app.state.models:
        raise HTTPException(404, f"model not found for {key}")
    obj = app.state.models[key]
    try:
        X = pd.DataFrame([req.features])[obj["features"]]
    except KeyError as e:
        raise HTTPException(400, f"missing feature: {e}")
    pred = float(obj["model"].predict(X)[0])
    return ForecastResponse(prediction=pred, target=req.target,
                            factory_id=req.factory_id)


@app.post("/anomaly", response_model=AnomalyResponse)
def anomaly(req: AnomalyRequest):
    if app.state.iso is None:
        raise HTTPException(503, "anomaly model not loaded")
    obj = app.state.iso
    base = pd.DataFrame([{
        "elec_consumption_kwh": req.elec_consumption_kwh,
        "steam_demand_t":       req.steam_demand_t,
        "gas_consumption_m3":   req.gas_consumption_m3,
        "water_intake_m3":      req.water_intake_m3,
        "production_t":         req.production_t,
        "boiler_efficiency":    req.boiler_efficiency,
        "turbine_power_mw":     req.turbine_power_mw,
    }])
    base["elec_per_t"]    = base["elec_consumption_kwh"] / max(base["production_t"], 0.1)
    base["steam_per_t"]   = base["steam_demand_t"]       / max(base["production_t"], 0.1)
    base["water_per_t"]   = base["water_intake_m3"]      / max(base["production_t"], 0.1)
    base["gas_per_steam"] = base["gas_consumption_m3"]   / max(base["steam_demand_t"], 0.1)
    X = base[obj["features"]]
    score = float(-obj["model"].decision_function(X)[0])
    return AnomalyResponse(
        is_anomaly=score > app.state.threshold,
        score=score,
        threshold=app.state.threshold,
    )


@app.get("/models")
def list_models():
    return {"models": [{"factory": k[0], "target": k[1]} for k in app.state.models]}
```

---

## 5) `Dockerfile` + `docker-compose.yml`

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501 8000

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

```yaml
# docker-compose.yml
version: "3.9"

services:
  dashboard:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./models:/app/models
      - ./ceuo_data.csv:/app/ceuo_data.csv
      - ./metrics.json:/app/metrics.json
    environment:
      - STREAMLIT_SERVER_HEADLESS=true
    restart: unless-stopped

  api:
    build: .
    command: uvicorn api:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models
      - ./metrics.json:/app/metrics.json
    restart: unless-stopped
```

---

## 6) اجرا

```bash
# 1) نصب
pip install -r requirements.txt

# 2) داده و مدل
python ceu_synthetic_data.py
python ceu_train_models.py
python ceu_evaluate_models.py

# 3) داشبورد
streamlit run app.py
# → http://localhost:8501

# 4) API (اختیاری، همزمان)
uvicorn api:app --port 8000
# → http://localhost:8000/docs

# 5) Docker
docker compose up --build
```

---

## 7) نمای کلی صفحات

| صفحه | محتوا |
|---|---|
| 🏠 نمای کلی | ۵ کارت KPI، نمودار دو محوره هزینه/تولید، سهم کارخانه‌ها، ترکیب هزینه |
| 📊 شاخص‌ها | ۴ نمودار شاخص ویژه + جدول مقایسه‌ای کارخانه‌ها |
| 🔮 پیش‌بینی | انتخاب کارخانه/هدف، نمودار واقعی vs پیش‌بینی، MAE/MAPE/R²، دانلود CSV |
| 🚨 انحراف | نمودار میله‌ای و پای، خط زمانی، جدول ۲۰۰ رخداد اخیر |
| ⚙️ بهینه‌سازی | اسلایدر پارامترها، اجرای بهینه‌سازی، ۴ کارت نتیجه، نمودار مقایسه پایه/بهینه |
| 🌊 آب/پساب | ۳ KPI، روند روزانه آب/پساب، جدول تفکیکی با بازچرخانی |
| 💰 هزینه | ۳ KPI، نمودار stack هزینه‌ها |
| 📄 گزارش‌ها | جدول متریک‌های مدل، F1/Precision/Recall/AUC، ۳ دکمه دانلود |

---

## 8) ویژگی‌های حرفه‌ای پیاده‌شده

- ✅ **تم تاریک مدرن** با CSS سفارشی (کارت‌های گرادیانی، سایه، hover)
- ✅ **چندصفحه‌ای** با ناوبری سایدبار
- ✅ **فیلتر سراسری** (کارخانه + بازه زمانی)
- ✅ **KPI کارت با دلتا** (مقایسه با ۷ روز قبل، رنگ سبز/قرمز هوشمند)
- ✅ **نمودارهای Plotly تعاملی** با hover یکپارچه
- ✅ **کش‌کردن داده و مدل** برای بارگذاری سریع
- ✅ **حالت خطا** (نبود داده/مدل)
- ✅ **دانلود CSV/JSON/MD**
- ✅ **API مستقل** با Swagger docs
- ✅ **Docker-ready**

