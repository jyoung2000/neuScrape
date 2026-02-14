#!/bin/sh
set -e

# Ensure data directories exist and are writable (runs after volume mount)
mkdir -p /data/wallpapers /data/logs /tmp/wallpaper-scraper
chown -R scraper:scraper /data /tmp/wallpaper-scraper 2>/dev/null || true

# Ensure Playwright browsers path is set for the scraper user
export PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# Drop to non-root user and exec the main process, preserving environment
exec su scraper -p -s /bin/sh -c "PLAYWRIGHT_BROWSERS_PATH=/opt/playwright exec $*"
