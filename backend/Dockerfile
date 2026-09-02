FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /app

# System libs needed by TensorFlow / pandas / openpyxl at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Persistent data (DB + trained models) lives here, mounted as a volume
ENV SISIP_DATA_DIR=/data \
    SISIP_DB_FILE=/data/sisip_database.db \
    SISIP_MODEL_DIR=/data/saved_models
RUN mkdir -p /data/saved_models

EXPOSE 5000

# Training requests can run for several minutes -> generous timeout, few workers
CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--workers", "2", "--threads", "2", "--timeout", "1800", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "app:app"]
