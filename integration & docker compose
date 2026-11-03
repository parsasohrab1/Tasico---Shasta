
بخش ۶ — یکپارچه‌سازی Airflow (گزارش روزانه)
افزودن به ceu_airflow_dag.py:

python
def generate_daily_report(**ctx):
    """تولید PDF گزارش روزانه و آرشیو"""
    import subprocess, sys
    from datetime import datetime
    script = os.path.join(PROJECT_DIR, "report_generator.py")
    result = subprocess.run(
        [sys.executable, script, "--days", "1"],
        cwd=PROJECT_DIR, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])
    print(result.stdout)

    # ارسال به storage/ایمیل (نمونه: ثبت مسیر در XCom)
    import glob
    latest = max(glob.glob(os.path.join(PROJECT_DIR, "reports", "*.pdf")),
                 key=os.path.getmtime)
    ctx["ti"].xcom_push(key="report_path", value=latest)
    print(f"report → {latest}")


def generate_weekly_report(**ctx):
    import subprocess, sys
    script = os.path.join(PROJECT_DIR, "report_generator.py")
    subprocess.run([sys.executable, script, "--days", "7"],
                   cwd=PROJECT_DIR, check=True)


# در DAG:
    t6 = PythonOperator(
        task_id="generate_daily_report",
        python_callable=generate_daily_report,
    )
    t7 = PythonOperator(
        task_id="generate_weekly_report",
        python_callable=generate_weekly_report,
        trigger_rule="none_failed",
    )

    t5 >> t6 >> t7
بخش ۷ — docker-compose.yml به‌روزرسانی‌شده
yaml
version: "3.9"

services:
  dashboard:
    build: .
    command: streamlit run app.py --server.port=8501 --server.address=0.0.0.0
    ports: ["8501:8501"]
    volumes:
      - ./models:/app/models
      - ./ceuo_data.csv:/app/ceuo_data.csv
      - ./metrics.json:/app/metrics.json
      - ./reports:/app/reports
      - ./fonts:/app/fonts
    environment:
      - WS_API_URL=http://ws:8090
    depends_on: [ws]
    restart: unless-stopped

  ws:
    build: .
    command: uvicorn ws_server:app --host 0.0.0.0 --port 8090
    ports: ["8090:8090"]
    environment:
      - KAFKA_BOOTSTRAP=${KAFKA_BOOTSTRAP:-}
      - KAFKA_TOPIC=ceuo.live
      - DEMO_MODE=${DEMO_MODE:-1}
    restart: unless-stopped

  api:
    build: .
    command: uvicorn api:app --host 0.0.0.0 --port 8000
    ports: ["8000:8000"]
    volumes:
      - ./models:/app/models
      - ./metrics.json:/app/metrics.json
    restart: unless-stopped

  # اختیاری — فقط اگر Kafka محلی می‌خواهید
  kafka:
    image: bitnami/kafka:3.6
    profiles: ["kafka"]
    ports: ["9092:9092"]
    environment:
      - KAFKA_CFG_NODE_ID=1
      - KAFKA_CFG_PROCESS_ROLES=broker,controller
      - KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=1@kafka:9093
      - KAFKA_CFG_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093
      - KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092
      - KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - ALLOW_PLAINTEXT_LISTENER=yes
