FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (minimal) for pymongo, numpy, redis, ssl
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m appuser
USER appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Expose FastAPI port
EXPOSE 8000

# Environment variables (override at runtime)
COPY .env .env


# Healthcheck (simple TCP check)
HEALTHCHECK CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',8000))" || exit 1

# Start app
CMD ["uvicorn", " src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]