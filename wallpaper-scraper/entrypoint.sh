#!/bin/sh
set -e

# Ensure data directories exist and are writable (runs after volume mount)
mkdir -p /data/wallpapers /data/logs /data/models /data/packages /tmp/wallpaper-scraper
chown -R scraper:scraper /data /tmp/wallpaper-scraper 2>/dev/null || true

# Install AI packages (torch, transformers) on first run if not already present
# They persist on the /data volume so this only runs once
if [ ! -f /data/packages/.installed ]; then
    echo "First startup: installing AI packages to /data/packages (one-time, ~2 min)..."
    pip install --no-cache-dir --target=/data/packages -r /app/requirements-ai.txt 2>&1 \
        && touch /data/packages/.installed \
        && echo "AI packages installed successfully." \
        || echo "WARNING: AI packages failed to install. Captioning will use color-based fallback."
    chown -R scraper:scraper /data/packages 2>/dev/null || true
fi

# Capture the full current environment (including docker-compose vars + Dockerfile ENV)
# in shell-sourceable format, so su doesn't strip them
export -p > /tmp/wallpaper-scraper/.env_runtime
chown scraper:scraper /tmp/wallpaper-scraper/.env_runtime 2>/dev/null || true

# Drop to non-root user, restore env vars, exec the main process
exec su scraper -s /bin/sh -c '. /tmp/wallpaper-scraper/.env_runtime; exec "$@"' -- "$@"
