FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --system --uid 10001 --create-home appuser
USER 10001:10001

EXPOSE 8000
CMD ["uvicorn", "tasico_shasta.api:app", "--host", "0.0.0.0", "--port", "8000"]
