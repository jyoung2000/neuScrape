FROM python:3.12-slim AS builder
WORKDIR /build

# Install lightweight dependencies only (no torch/transformers — those install at first startup)
COPY requirements.txt .
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium \
    && rm -rf /tmp/* /root/.cache

FROM python:3.12-slim
WORKDIR /app

# System dependencies for Playwright + Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libgbm1 libasound2 libxshmfence1 \
    libjpeg62-turbo libwebp7 libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages and Playwright browser from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /opt/playwright /opt/playwright

COPY . .

# Playwright browser path
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# AI packages (torch, transformers) install at first startup to /data/packages
# HuggingFace model weights cache to /data/models — both persist on the volume
ENV PYTHONPATH=/data/packages
ENV HF_HOME=/data/models
ENV TRANSFORMERS_CACHE=/data/models/hub

# Create non-root user and set permissions
RUN useradd -m scraper \
    && mkdir -p /data/wallpapers /data/logs /data/models /data/packages /tmp/wallpaper-scraper \
    && chown -R scraper:scraper /app /data /tmp/wallpaper-scraper \
    && chmod -R o+rx /opt/playwright \
    && chmod +x /app/entrypoint.sh

EXPOSE 1629
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:1629/health')" || exit 1

# Entrypoint installs AI packages on first run, then drops to scraper user
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "1629"]
