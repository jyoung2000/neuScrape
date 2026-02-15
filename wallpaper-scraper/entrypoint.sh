#!/bin/sh
set -e

# Ensure data directories exist and are writable (runs after volume mount)
mkdir -p /data/wallpapers /data/logs /data/models /tmp/wallpaper-scraper
chown -R scraper:scraper /data /tmp/wallpaper-scraper 2>/dev/null || true

# Capture the full current environment (including docker-compose vars + Dockerfile ENV)
# in shell-sourceable format, so su doesn't strip them
export -p > /tmp/wallpaper-scraper/.env_runtime
chown scraper:scraper /tmp/wallpaper-scraper/.env_runtime 2>/dev/null || true

# Drop to non-root user, restore env vars, exec the main process
exec su scraper -s /bin/sh -c '. /tmp/wallpaper-scraper/.env_runtime; exec "$@"' -- "$@"
