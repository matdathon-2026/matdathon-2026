# Single image shared by the API container app and the ingestion job.
# The job overrides the command, so both always run identical code.

FROM node:22-alpine AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci || npm install
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    COPILOT_CLI_EXTRACT_DIR=/opt/copilot-runtime

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

# The Copilot runtime binary is downloaded at build time so that the first
# judged request never waits on a download (TRD 17.2).
RUN pip install --no-cache-dir -r requirements.txt \
    && (python -m copilot download-runtime || echo "copilot runtime prefetch skipped") \
    && chmod -R a+rX /opt/copilot-runtime 2>/dev/null || true

ENV COPILOT_SKIP_CLI_DOWNLOAD=1

COPY app/ ./app/
COPY data/ ./data/
COPY --from=web /web/dist ./web/dist

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
