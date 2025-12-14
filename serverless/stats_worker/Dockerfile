FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for mysqlclient
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install backend deps + worker deps
COPY backend/requirements.txt /app/requirements.txt
COPY serverless/stats_worker/requirements.txt /app/worker-requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/worker-requirements.txt

# Copy backend code and worker
COPY backend /app/backend
COPY serverless/stats_worker /app/serverless/stats_worker

ENV DJANGO_SETTINGS_MODULE=project.settings
ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["uvicorn", "serverless.stats_worker.main:app", "--host", "0.0.0.0", "--port", "8080"]
