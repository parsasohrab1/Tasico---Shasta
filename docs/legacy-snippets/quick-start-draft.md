
بخش ۸ — تست سریع
bash
# 1) PDF
python report_generator.py --days 30
# → reports/ceuo_report_YYYYMMDD_HHMM.pdf

# 2) همه دوره‌ها
python report_generator.py --all

# 3) WebSocket (حالت demo)
DEMO_MODE=1 uvicorn ws_server:app --port 8090
# مرورگر: http://localhost:8090/live/client

# 4) تست REST
curl http://localhost:8090/live/latest
curl http://localhost:8090/health

# 5) داشبورد (با صفحه زنده)
streamlit run app.py

# 6) همه با هم
docker compose up --build
# - dashboard : http://localhost:8501
# - ws        : http://localhost:8090/live/client
# - api       : http://localhost:8000/docs

# 7) Kafka واقعی
KAFKA_BOOTSTRAP=localhost:9092 DEMO_MODE=0 docker compose --profile kafka up
