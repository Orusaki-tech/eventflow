FROM python:3.12-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --user -r requirements.txt


FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:${PATH}"

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local

COPY eventflow/ /app/eventflow/
COPY migrations/ /app/migrations/
COPY alembic.ini pyproject.toml .env.example /app/

EXPOSE 8000

CMD ["uvicorn", "eventflow.entrypoints.fastapi_app:app", "--host", "0.0.0.0", "--port", "8000"]
