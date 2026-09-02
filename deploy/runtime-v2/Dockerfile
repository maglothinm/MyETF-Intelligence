FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/polititrack

COPY requirements-tracker.txt requirements-ai.txt requirements-vault.txt requirements-runtime-v2.txt ./
RUN pip install --no-cache-dir -r requirements-runtime-v2.txt \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY backend ./backend
COPY config ./config
COPY migrations ./migrations
COPY runtime_v2 ./runtime_v2
COPY schemas ./schemas
COPY scripts ./scripts

RUN useradd --create-home --uid 10001 polititrack \
    && chown -R polititrack:polititrack /srv/polititrack /ms-playwright
USER polititrack

CMD ["python", "-m", "runtime_v2", "--help"]
