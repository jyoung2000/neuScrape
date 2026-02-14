#!/bin/sh
set -e

# Ensure data directories exist and are writable (runs after volume mount)
mkdir -p /data/wallpapers /data/logs /tmp/wallpaper-scraper
chown -R scraper:scraper /data /tmp/wallpaper-scraper 2>/dev/null || true

# Drop to non-root user and exec the main process
exec su scraper -s /bin/sh -c "exec $*"
