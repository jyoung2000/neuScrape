FROM python:3.12-slim
WORKDIR /app

# System dependencies for Playwright + Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libgbm1 libasound2 libxshmfence1 \
    libjpeg62-turbo libwebp7 libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (lightweight only — no torch/scipy)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /tmp/* /root/.cache

# Playwright browser
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN playwright install chromium \
    && rm -rf /tmp/*

COPY . .

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
