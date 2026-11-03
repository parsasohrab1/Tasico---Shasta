
ws_server.py
python
"""
CEUO Live WebSocket Server
- FastAPI WebSocket endpoint برای push داده زنده
- Consumer از Kafka (topic: ceuo.live) با fallback به داده مصنوعی
- Broadcast به همه کلاینت‌های متصل
- REST endpoint /live/latest برای Streamlit

اجرا: uvicorn ws_server:app --host 0.0.0.0 --port 8090
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Set

import numpy as np
import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

# ---------------------------------------------------------------------
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "")
KAFKA_TOPIC     = os.environ.get("KAFKA_TOPIC", "ceuo.live")
DEMO_MODE       = os.environ.get("DEMO_MODE", "1") == "1"
SNAPSHOT_FILE   = "live_snapshot.json"   # آخرین وضعیت برای REST

app = FastAPI(title="CEUO Live", version="1.0.0")

clients: Set[WebSocket] = set()
latest_snapshot: dict = {"ts": None, "factories": {}}
lock = asyncio.Lock()


# ---------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------
async def register(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    async with lock:
        if latest_snapshot["ts"]:
            await ws.send_text(json.dumps(latest_snapshot, default=str))


async def unregister(ws: WebSocket):
    clients.discard(ws)


async def broadcast(payload: dict):
    if not clients:
        return
    msg = json.dumps(payload, default=str)
    dead = []
    for ws in list(clients):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


# ---------------------------------------------------------------------
# Snapshot builder
# ---------------------------------------------------------------------
def build_snapshot(row: dict) -> dict:
    return {
        "ts": row["ts"],
        "factories": row["factories"],
        "totals": {
            "cost_usd":  sum(f["cost_usd"]  for f in row["factories"].values()),
            "elec_kwh":  sum(f["elec_kwh"]  for f in row["factories"].values()),
            "steam_t":   sum(f["steam_t"]   for f in row["factories"].values()),
            "water_m3":  sum(f["water_m3"]  for f in row["factories"].values()),
            "production_t": sum(f["production_t"] for f in row["factories"].values()),
        },
    }


# ---------------------------------------------------------------------
# Kafka consumer (production mode)
# ---------------------------------------------------------------------
async def kafka_consumer():
    from aiokafka import AIOKafkaConsumer
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="ceu-ws",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
    )
    await consumer.start()
    print(f"✓ Kafka consumer connected: {KAFKA_BOOTSTRAP}/{KAFKA_TOPIC}")
    try:
        async for msg in consumer:
            payload = msg.value
            snap = build_snapshot(payload)
            async with lock:
                global latest_snapshot
                latest_snapshot = snap
            await broadcast(snap)
    finally:
        await consumer.stop()


# ---------------------------------------------------------------------
# Demo producer (fallback)
# ---------------------------------------------------------------------
FACTORIES = ["F1-PAPER", "F2-TISSUE", "F3-WOOD"]

async def demo_producer():
    print("✓ demo producer started (synthetic live data every 5s)")
    rng = np.random.default_rng()
    t0 = datetime.utcnow()

    while True:
        t = (datetime.utcnow() - t0).total_seconds()
        factories = {}
        for i, f in enumerate(FACTORIES):
            base_prod = [12, 9, 15][i]
            wave = np.sin(t / 60 + i) * 2
            prod = max(0.0, base_prod + wave + rng.normal(0, 0.5))
            elec = prod * 600 * (1 + rng.normal(0, 0.03))
            steam = prod * 2.8 * (1 + rng.normal(0, 0.03))
            gas = steam * 7.5 / 0.87
            water = prod * 18 * (1 + rng.normal(0, 0.03))
            cost = elec * 0.10 + gas * 0.15 + water * 0.8

            factories[f] = {
                "production_t": round(prod, 2),
                "elec_kwh":     round(elec, 1),
                "steam_t":      round(steam, 2),
                "gas_m3":       round(gas, 1),
                "water_m3":     round(water, 1),
                "cost_usd":     round(cost, 2),
            }

        payload = {"ts": datetime.utcnow().isoformat(), "factories": factories}
        snap = build_snapshot(payload)

        async with lock:
            global latest_snapshot
            latest_snapshot = snap
            with open(SNAPSHOT_FILE, "w") as f:
                json.dump(snap, f, default=str)

        await broadcast(snap)
        await asyncio.sleep(5)


# ---------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    if DEMO_MODE or not KAFKA_BOOTSTRAP:
        app.state.task = asyncio.create_task(demo_producer())
    else:
        app.state.task = asyncio.create_task(kafka_consumer())


@app.on_event("shutdown")
async def shutdown():
    t = getattr(app.state, "task", None)
    if t:
        t.cancel()


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": "demo" if (DEMO_MODE or not KAFKA_BOOTSTRAP) else "kafka",
        "clients": len(clients),
        "has_snapshot": latest_snapshot["ts"] is not None,
    }


@app.get("/live/latest")
async def live_latest():
    async with lock:
        return JSONResponse(latest_snapshot)


@app.get("/live/client", response_class=HTMLResponse)
async def live_client_page():
    with open("ws_client.html", encoding="utf-8") as f:
        return f.read()


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await register(ws)
    try:
        while True:
            # نگه‌داشتن اتصال باز؛ پیام از کلاینت نادیده گرفته می‌شود
            await ws.receive_text()
    except WebSocketDisconnect:
        await unregister(ws)
    except Exception:
        await unregister(ws)
ws_client.html
html
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>CEUO — نمایش زنده</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  body { font-family: sans-serif; background: #0F172A; color: #E2E8F0; margin: 0; padding: 20px; }
  h1 { color: #60A5FA; font-size: 22px; margin: 0 0 6px 0; }
  .status { font-size: 12px; color: #94A3B8; }
  .status .dot { display: inline-block; width: 8px; height: 8px;
                 border-radius: 50%; background: #EF4444; margin-left: 6px; }
  .status .dot.on { background: #10B981; }
  .grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin: 16px 0; }
  .card { background: #1E293B; border: 1px solid #334155; border-radius: 10px; padding: 14px; }
  .card .label { color: #94A3B8; font-size: 12px; }
  .card .value { font-size: 22px; font-weight: bold; margin-top: 4px; }
  .card .unit { color: #64748B; font-size: 12px; font-weight: normal; margin-right: 4px; }
  .chart-box { background: #1E293B; border: 1px solid #334155; border-radius: 10px;
               padding: 14px; margin-top: 12px; height: 320px; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12px; }
  th { background: #1E293B; color: #60A5FA; padding: 8px; }
  td { padding: 6px 8px; border-bottom: 1px solid #334155; }
  .ts { color: #64748B; font-size: 11px; }
</style>
</head>
<body>

<h1>⚡ نمایش زنده — CEUO</h1>
<div class="status">وضعیت: <span class="dot" id="dot"></span><span id="state">اتصال…</span>
  · آخرین به‌روزرسانی: <span id="ts">—</span>
  · تعداد پیام: <span id="n">0</span></div>

<div class="grid">
  <div class="card"><div class="label">تولید</div>
    <div class="value"><span id="v-prod">—</span><span class="unit">ton/h</span></div></div>
  <div class="card"><div class="label">برق</div>
    <div class="value"><span id="v-elec">—</span><span class="unit">kWh</span></div></div>
  <div class="card"><div class="label">بخار</div>
    <div class="value"><span id="v-steam">—</span><span class="unit">ton</span></div></div>
  <div class="card"><div class="label">آب</div>
    <div class="value"><span id="v-water">—</span><span class="unit">m³</span></div></div>
  <div class="card"><div class="label">هزینه</div>
    <div class="value"><span id="v-cost">—</span><span class="unit">$</span></div></div>
</div>

<div class="chart-box"><canvas id="chart"></canvas></div>

<table>
  <thead><tr>
    <th>کارخانه</th><th>تولید</th><th>برق</th><th>بخار</th><th>گاز</th><th>آب</th><th>هزینه</th>
  </tr></thead>
  <tbody id="tbody"></tbody>
</table>

<script>
const WS_URL = (location.protocol === 'https:' ? 'wss://' : 'ws://')
             + location.host + '/ws/live';

const MAX_POINTS = 30;
let labels = [];
let series = { prod: [], cost: [] };
let msgCount = 0;

const $ = id => document.getElementById(id);

const chart = new Chart($('chart'), {
  type: 'line',
  data: {
    labels,
    datasets: [
      { label: 'تولید (ton/h)', data: series.prod,
        borderColor: '#3B82F6', backgroundColor: 'rgba(59,130,246,.1)',
        tension: .35, fill: true },
      { label: 'هزینه ($)', data: series.cost,
        borderColor: '#F59E0B', backgroundColor: 'rgba(245,158,11,.1)',
        tension: .35, yAxisID: 'y2' },
    ],
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: '#E2E8F0' } } },
    scales: {
      x: { ticks: { color: '#94A3B8' }, grid: { color: '#334155' } },
      y: { ticks: { color: '#94A3B8' }, grid: { color: '#334155' } },
      y2: { position: 'right', ticks: { color: '#F59E0B' },
            grid: { drawOnChartArea: false } },
    },
  },
});

function fmt(n, dec = 0) {
  if (n == null) return '—';
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: dec });
}

function onMessage(data) {
  msgCount++;
  $('n').textContent = msgCount;
  $('ts').textContent = new Date(data.ts).toLocaleTimeString('fa-IR');
  $('dot').classList.add('on');
  $('state').textContent = 'متصل';

  const t = data.totals;
  $('v-prod').textContent  = fmt(t.production_t, 1);
  $('v-elec').textContent  = fmt(t.elec_kwh);
  $('v-steam').textContent = fmt(t.steam_t, 1);
  $('v-water').textContent = fmt(t.water_m3);
  $('v-cost').textContent  = fmt(t.cost_usd, 0);

  // table
  const rows = Object.entries(data.factories).map(([f, v]) =>
    `<tr><td>${f}</td>
      <td>${fmt(v.production_t, 1)}</td>
      <td>${fmt(v.elec_kwh)}</td>
      <td>${fmt(v.steam_t, 1)}</td>
      <td>${fmt(v.gas_m3)}</td>
      <td>${fmt(v.water_m3)}</td>
      <td>${fmt(v.cost_usd, 0)}</td></tr>`
  ).join('');
  $('tbody').innerHTML = rows;

  // chart
  labels.push(new Date(data.ts).toLocaleTimeString('fa-IR'));
  series.prod.push(t.production_t);
  series.cost.push(t.cost_usd);
  if (labels.length > MAX_POINTS) {
    labels.shift(); series.prod.shift(); series.cost.shift();
  }
  chart.update('none');
}

function connect() {
  const ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    $('dot').classList.add('on');
    $('state').textContent = 'متصل';
    ws.send('hello');
  };
  ws.onmessage = e => {
    try { onMessage(JSON.parse(e.data)); } catch (err) { console.error(err); }
  };
  ws.onclose = () => {
    $('dot').classList.remove('on');
    $('state').textContent = 'قطع — تلاش مجدد در ۳ ثانیه';
    setTimeout(connect, 3000);
  };
  ws.onerror = () => ws.close();
}

connect();
</script>
</body>
</html>
app_live_snippet.py — یکپارچه‌سازی با Streamlit
python
"""
این snippet را در app.py به‌عنوان یک صفحه جدید اضافه کنید.

برای نمایش زنده در Streamlit:
  pip install streamlit-autorefresh
"""

import os
import json
import requests
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

WS_API = os.environ.get("WS_API_URL", "http://localhost:8090")


# ---------------------------------------------------------------------
def fetch_latest():
    try:
        r = requests.get(f"{WS_API}/live/latest", timeout=3)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def page_live():
    st.markdown("### 🔴 نمایش زنده")

    if HAS_AUTOREFRESH:
        st_autorefresh(interval=5_000, key="live_tick")
    else:
        st.caption("نصب `streamlit-autorefresh` برای به‌روزرسانی خودکار توصیه می‌شود.")

    snap = fetch_latest()
    if not snap or not snap.get("ts"):
        st.warning("سرویس زنده پاسخ نمی‌دهد. `uvicorn ws_server:app --port 8090` را اجرا کنید.")
        return

    t = snap["totals"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("تولید", f"{t['production_t']:,.1f}", "ton/h")
    c2.metric("برق",   f"{t['elec_kwh']:,.0f}",   "kWh")
    c3.metric("بخار",  f"{t['steam_t']:,.1f}",    "ton")
    c4.metric("آب",    f"{t['water_m3']:,.0f}",   "m³")
    c5.metric("هزینه", f"${t['cost_usd']:,.0f}",  "USD")

    # تاریخچه در session_state
    if "live_hist" not in st.session_state:
        st.session_state.live_hist = []
    hist = st.session_state.live_hist
    hist.append({
        "ts": snap["ts"],
        "prod": t["production_t"],
        "cost": t["cost_usd"],
    })
    if len(hist) > 60:
        hist.pop(0)
    hdf = pd.DataFrame(hist)
    hdf["ts"] = pd.to_datetime(hdf["ts"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hdf["ts"], y=hdf["prod"], name="تولید",
                             line=dict(color="#3B82F6", width=2)))
    fig.add_trace(go.Scatter(x=hdf["ts"], y=hdf["cost"], name="هزینه",
                             yaxis="y2", line=dict(color="#F59E0B", width=2)))
    fig.update_layout(
        height=340, template="plotly_dark",
        yaxis=dict(title="تولید"),
        yaxis2=dict(title="هزینه", overlaying="y", side="right"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=20, b=10),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # جدول
    rows = []
    for f, v in snap["factories"].items():
        rows.append({
            "کارخانه": f,
            "تولید": v["production_t"],
            "برق": v["elec_kwh"],
            "بخار": v["steam_t"],
            "آب": v["water_m3"],
            "هزینه $": v["cost_usd"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.caption(
        f"آخرین به‌روزرسانی: {snap['ts']}  ·  "
        f"[نمایش تمام‌صفحه]({WS_API}/live/client)"
    )
افزودن به app.py:

python
# در sidebar radio، یک آیتم اضافه کنید:
"🔴 نمایش زنده",

# در routes:
"🔴 نمایش زنده": lambda df: __import__("app_live_snippet").page_live(),
