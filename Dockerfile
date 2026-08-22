# syntax=docker/dockerfile:1

# ---------- Stage 1: build the React frontend ----------
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

# ---------- Stage 2: Python runtime ----------
# Python 3.11 is the verified-compatible version. 3.10 is incompatible with
# agent-framework-github-copilot; 3.12 is unverified.
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # The Copilot runtime binary ships bundled inside the wheel
    # (copilot/bin/copilot). No runtime download happens.
    COPILOT_SKIP_CLI_DOWNLOAD=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code + seed data
COPY app/ ./app/
COPY data/ ./data/

# Built frontend from stage 1, served by FastAPI as static files
COPY --from=web /web/dist ./web/dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
