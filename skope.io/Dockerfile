# Build from repo root for full Lumibot, or from skope.io for API-only.
#   docker build -f skope.io/Dockerfile -t skope-io .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/skope.io:/app

WORKDIR /app

# Lumibot package sources (local monorepo install).
COPY setup.py README.md requirements.txt MANIFEST.in pyproject.toml /app/
COPY lumibot /app/lumibot
COPY skope.io /app/skope.io

RUN pip install --upgrade pip \
    && (pip install -e /app || pip install lumibot) \
    && pip install -r /app/skope.io/requirements.txt

WORKDIR /app/skope.io
EXPOSE 8080
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
