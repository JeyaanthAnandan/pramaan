# Pramaan: one Cloud Run container = FastAPI API + built React SPA (one cold start).
# ---- frontend build
FROM node:22.11.0-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- runtime
FROM python:3.12.7-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8080 \
    PRAMAAN_STATIC_DIR=/srv/static PRAMAAN_DEMO_DIR=/srv/demo PRAMAAN_REGULATION_DIR=/srv/regulation PRAMAAN_DATA_DIR=/tmp/pramaan
# WeasyPrint needs Pango; fonts for Devanagari/Tamil in PDFs
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 fonts-noto-core fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/app ./app
COPY backend/refdata/json ./refdata/json
COPY backend/refdata/manifest.json ./refdata/manifest.json
COPY backend/eval/metrics.json* ./eval/
COPY demo/ground_truth.json /srv/demo/ground_truth.json
COPY demo/out /srv/demo/out
COPY demo/cache /srv/demo/cache
COPY demo/supplier /srv/demo/supplier
COPY docs/regulation/*.pdf /srv/regulation/
# parse the EC guidance once here, so a new instance answers its first copilot question in seconds
RUN PRAMAAN_DATA_DIR=/srv/regulation python -c "from app.copilot.service import corpus; print(len(corpus()), 'copilot chunks')"
COPY --from=web /web/dist /srv/static
RUN useradd --uid 10001 --create-home pramaan && mkdir -p /tmp/pramaan && chown -R pramaan /tmp/pramaan
USER pramaan
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 75 --proxy-headers --forwarded-allow-ips=*"]
