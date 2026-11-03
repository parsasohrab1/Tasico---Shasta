بخش ۴ — گزارش PDF خودکار
requirements.txt — افزودنی‌ها
txt
weasyprint>=60.0
jinja2>=3.1
aiokafka>=0.10
websockets>=12.0
streamlit-autorefresh>=1.0
report_template.html
html
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<style>
  @font-face {
    font-family: 'Vazir';
    src: url('fonts/Vazirmatn-Regular.ttf');
  }
  @font-face {
    font-family: 'Vazir';
    src: url('fonts/Vazirmatn-Bold.ttf');
    font-weight: bold;
  }
  body { font-family: 'Vazir', sans-serif; color: #1F2937; font-size: 11pt; margin: 30px; }
  .cover {
    text-align: center; padding: 90px 20px; border-bottom: 4px solid #2563EB;
    background: linear-gradient(135deg, #EFF6FF, #FFFFFF);
    page-break-after: always;
  }
  .cover h1 { color: #1E40AF; font-size: 26pt; margin: 10px 0; }
  .cover .sub { color: #64748B; font-size: 13pt; margin-top: 8px; }
  .cover .meta { color: #94A3B8; font-size: 10pt; margin-top: 40px; }
  .section { margin-top: 28px; page-break-inside: avoid; }
  h2 { color: #1E40AF; border-bottom: 2px solid #DBEAFE; padding-bottom: 6px; font-size: 15pt; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 10pt; }
  th { background: #EFF6FF; color: #1E40AF; padding: 8px; text-align: right; }
  td { padding: 8px; border-bottom: 1px solid #E5E7EB; text-align: right; }
  tr:nth-child(even) td { background: #F9FAFB; }
  .kpi-grid { display: flex; gap: 12px; margin: 16px 0; }
  .kpi {
    flex: 1; background: #F0F9FF; border-right: 4px solid #2563EB;
    padding: 14px; border-radius: 6px;
  }
  .kpi .label { color: #64748B; font-size: 10pt; }
  .kpi .value { color: #1E293B; font-size: 18pt; font-weight: bold; margin-top: 4px; }
  .badge-ok { background: #D1FAE5; color: #065F46; padding: 2px 8px; border-radius: 10px; font-size: 9pt; }
  .badge-warn { background: #FEF3C7; color: #92400E; padding: 2px 8px; border-radius: 10px; font-size: 9pt; }
  .footer { position: fixed; bottom: 15px; left: 30px; right: 30px;
            font-size: 8pt; color: #94A3B8; border-top: 1px solid #E5E7EB; padding-top: 6px; }
</style>
</head>
<body>

<div class="cover">
  <div style="font-size: 42pt;">⚡</div>
  <h1>گزارش انرژی CEUO</h1>
  <div class="sub">سامانه هوشمند بهینه‌سازی انرژی و سامانه‌های جانبی کارخانه‌های سلولزی</div>
  <div class="meta">
    هلدینگ سلولزی تأمین گسترش نوین (تاسیکو)<br>
    دوره گزارش: {{ period_start }} تا {{ period_end }}<br>
    تاریخ تولید: {{ generated_at }}<br>
    شناسه گزارش: {{ report_id }}
  </div>
</div>

<div class="section">
  <h2>۱. خلاصه اجرایی</h2>
  <div class="kpi-grid">
    <div class="kpi"><div class="label">هزینه انرژی کل</div>
      <div class="value">{{ "{:,.0f}".format(total_cost) }} $</div></div>
    <div class="kpi"><div class="label">تولید کل</div>
      <div class="value">{{ "{:,.0f}".format(total_prod) }} ton</div></div>
    <div class="kpi"><div class="label">شاخص ویژه برق</div>
      <div class="value">{{ "{:,.0f}".format(sec_elec) }} kWh/ton</div></div>
    <div class="kpi"><div class="label">رخداد انحراف</div>
      <div class="value">{{ n_anomaly }}</div></div>
  </div>
</div>

<div class="section">
  <h2>۲. عملکرد کارخانه‌ها</h2>
  <table>
    <tr>
      <th>کارخانه</th><th>تولید (ton)</th><th>برق (kWh)</th>
      <th>بخار (ton)</th><th>گاز (m³)</th><th>آب (m³)</th>
    </tr>
    {% for r in factories %}
    <tr>
      <td>{{ r.factory_id }}</td>
      <td>{{ "{:,.0f}".format(r.production) }}</td>
      <td>{{ "{:,.0f}".format(r.elec) }}</td>
      <td>{{ "{:,.0f}".format(r.steam) }}</td>
      <td>{{ "{:,.0f}".format(r.gas) }}</td>
      <td>{{ "{:,.0f}".format(r.water) }}</td>
    </tr>
    {% endfor %}
  </table>
</div>

<div class="section">
  <h2>۳. رخدادهای انحراف</h2>
  {% if anomalies %}
  <table>
    <tr><th>زمان</th><th>کارخانه</th><th>نوع</th><th>شدت</th></tr>
    {% for a in anomalies %}
    <tr>
      <td>{{ a.timestamp }}</td>
      <td>{{ a.factory_id }}</td>
      <td>{{ a.anomaly_type }}</td>
      <td><span class="badge-warn">{{ a.severity }}</span></td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p>رخداد انحرافی در این دوره ثبت نشده است.</p>
  {% endif %}
</div>

<div class="section">
  <h2>۴. دقت مدل‌های پیش‌بینی</h2>
  {% if metrics %}
  <table>
    <tr><th>کارخانه</th><th>هدف</th><th>MAE</th><th>MAPE %</th><th>R²</th></tr>
    {% for m in metrics %}
    <tr>
      <td>{{ m.factory }}</td><td>{{ m.target }}</td>
      <td>{{ "{:,.1f}".format(m.mae) }}</td>
      <td>{{ "{:.2f}".format(m.mape) }}</td>
      <td>{{ "{:.3f}".format(m.r2) }}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}
</div>

<div class="section">
  <h2>۵. صرفه‌جویی برآوردی</h2>
  <p>بر اساس دقت مدل‌ها و بازه گزارش:</p>
  <table>
    <tr><th>مبنای محاسبه</th><th>مقدار</th></tr>
    <tr><td>هزینه پایه</td><td>{{ "{:,.0f}".format(cost_baseline) }} $</td></tr>
    <tr><td>نرخ صرفه‌جویی</td><td>{{ "{:.2f}".format(savings_rate) }} %</td></tr>
    <tr><td><b>صرفه‌جویی برآوردی</b></td><td><b>{{ "{:,.0f}".format(savings) }} $</b></td></tr>
  </table>
</div>

<div class="footer">
  CEUO — گزارش خودکار | {{ generated_at }} | صفحه <span class="page"></span>
</div>

</body>
</html>
report_generator.py
python
"""
CEUO Automatic PDF Report Generator
- Jinja2 + WeasyPrint (RTL native, فونت Vazir)
- خروجی: reports/ceuo_report_YYYYMMDD_HHMM.pdf
- قابل فراخوانی از CLI، Airflow، API و داشبورد
"""

import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import json
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

# ---------------------------------------------------------------------
DATA       = "ceuo_data.csv"
METRICS_J  = "metrics.json"
TEMPLATE_D = "."
OUT_DIR    = "reports"
FONT_DIR   = "fonts"

os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------
def prepare_context(df: pd.DataFrame, metrics: dict, days: int = 30):
    end   = df["timestamp"].max()
    start = end - timedelta(days=days)
    sub   = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()

    # KPI
    total_cost = float(sub[["cost_elec_usd", "cost_gas_usd",
                            "cost_water_usd", "cost_wastewater_usd"]].sum().sum())
    total_prod = float(sub["production_t"].sum())
    sec_elec   = float(sub["elec_consumption_kwh"].sum() / max(total_prod, 1))
    n_anomaly  = int(sub["anomaly_flag"].sum())

    # factories table
    agg = sub.groupby("factory_id").agg({
        "production_t": "sum",
        "elec_consumption_kwh": "sum",
        "steam_demand_t": "sum",
        "gas_consumption_m3": "sum",
        "water_intake_m3": "sum",
    }).reset_index()
    factories = [{
        "factory_id": r.factory_id,
        "production": r.production_t,
        "elec": r.elec_consumption_kwh,
        "steam": r.steam_demand_t,
        "gas": r.gas_consumption_m3,
        "water": r.water_intake_m3,
    } for r in agg.itertuples()]

    # anomalies (max 20)
    anom = sub[sub["anomaly_flag"] == 1].copy()
    anom["severity"] = np.where(
        anom["elec_consumption_kwh"] > sub["elec_consumption_kwh"].quantile(0.95),
        "بالا", "متوسط",
    )
    anomalies = [{
        "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M"),
        "factory_id": r.factory_id,
        "anomaly_type": r.anomaly_type,
        "severity": r.severity,
    } for r in anom.head(20).itertuples()]

    # metrics
    m_rows = []
    if metrics and "forecast" in metrics:
        for k, v in metrics["forecast"].items():
            fid, tgt = k.split("__", 1)
            m_rows.append({
                "factory": fid, "target": tgt,
                "mae": v["MAE"], "mape": v["MAPE"], "r2": v["R2"],
            })

    # savings
    cost_baseline = float(sub[["cost_elec_usd", "cost_gas_usd",
                               "cost_water_usd", "cost_wastewater_usd"]].sum().sum())
    savings_rate  = 0.0
    if metrics and "forecast" in metrics:
        avg_mape = np.mean([v["MAPE"] for v in metrics["forecast"].values()])
        savings_rate = min(0.003 * avg_mape * 100, 0.10) * 100
    savings = cost_baseline * savings_rate / 100

    return {
        "period_start": start.strftime("%Y-%m-%d"),
        "period_end":   end.strftime("%Y-%m-%d"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "report_id":    f"CEUO-{uuid.uuid4().hex[:8].upper()}",
        "total_cost":   total_cost,
        "total_prod":   total_prod,
        "sec_elec":     sec_elec,
        "n_anomaly":    n_anomaly,
        "factories":    factories,
        "anomalies":    anomalies,
        "metrics":      m_rows,
        "cost_baseline": cost_baseline,
        "savings_rate":  savings_rate,
        "savings":       savings,
    }


# ---------------------------------------------------------------------
def render_html(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATE_D), autoescape=True)
    tpl = env.get_template("report_template.html")
    return tpl.render(**context)


def render_pdf(html: str, out_path: str):
    # embedded font (اگر موجود باشد)
    base_url = Path(TEMPLATE_D).resolve()
    HTML(string=html, base_url=str(base_url)).write_pdf(
        out_path,
        stylesheets=[CSS(string="@page { size: A4; margin: 20mm; }")]
    )


# ---------------------------------------------------------------------
def generate(days: int = 30, out_path: str | None = None) -> str:
    if not os.path.exists(DATA):
        raise FileNotFoundError(f"{DATA} not found")

    df = pd.read_csv(DATA, parse_dates=["timestamp"])
    metrics = None
    if os.path.exists(METRICS_J):
        with open(METRICS_J, encoding="utf-8") as f:
            metrics = json.load(f)

    ctx = prepare_context(df, metrics, days=days)
    html = render_html(ctx)

    if out_path is None:
        out_path = os.path.join(
            OUT_DIR,
            f"ceuo_report_{datetime.now():%Y%m%d_%H%M}.pdf",
        )
    render_pdf(html, out_path)
    return out_path


# ---------------------------------------------------------------------
def generate_all_periods(base_dir: str = OUT_DIR):
    """گزارش‌های روزانه، هفتگی، ماهانه"""
    outs = []
    for days, name in [(1, "daily"), (7, "weekly"), (30, "monthly")]:
        p = os.path.join(base_dir, f"ceuo_{name}_{datetime.now():%Y%m%d}.pdf")
        generate(days=days, out_path=p)
        outs.append(p)
        print(f"  ✓ {name:8s} → {p}")
    return outs


# ---------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        generate_all_periods()
    else:
        p = generate(days=args.days, out_path=args.out)
        print(f"PDF → {p}")
نصب فونت
bash
mkdir -p fonts
# دانلود Vazirmatn از https://github.com/rastikerdar/vazirmatn/releases
# سپس:
cp Vazirmatn-Regular.ttf Vazirmatn-Bold.ttf fonts/
