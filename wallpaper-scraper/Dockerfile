FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app

# System dependencies for Playwright + Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libgbm1 libasound2 libxshmfence1 \
    libjpeg62-turbo libwebp7 libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY . .

# Use shared locations for Playwright and HuggingFace so both root (build) and scraper (runtime) can access them
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
ENV HF_HOME=/opt/huggingface
ENV TRANSFORMERS_CACHE=/opt/huggingface/hub

# Install Playwright Chromium (system deps already installed above via apt-get)
RUN playwright install chromium \
    && rm -rf /tmp/* /root/.cache/pip

# Pre-download AI model weights during build (so container starts instantly)
# Then clean up root's HF cache (token file, etc) — models live in /opt/huggingface
RUN python scripts/download_model.py \
    && rm -rf /root/.cache/huggingface /root/.cache/pip /tmp/*
ENV HF_HUB_OFFLINE=1

# Create non-root user and set permissions
RUN useradd -m scraper \
    && mkdir -p /data/wallpapers /data/logs /tmp/wallpaper-scraper \
    && chown -R scraper:scraper /app /data /tmp/wallpaper-scraper \
    && chmod -R o+rx /opt/playwright \
    && chmod -R o+rx /opt/huggingface \
    && chmod +x /app/entrypoint.sh

EXPOSE 1629
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:1629/health')" || exit 1

# Entrypoint creates dirs after volume mount, then drops to scraper user
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "1629"]
