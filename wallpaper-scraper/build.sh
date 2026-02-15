#!/bin/bash
set -e

echo "=== Wallpaper Scraper: Clean Docker Build ==="
echo ""

# Step 1: Free disk space by purging Docker build cache and dangling images
echo "[1/3] Pruning Docker build cache and dangling images..."
docker builder prune -af 2>/dev/null || true
docker image prune -f 2>/dev/null || true
echo "  Done."

# Step 2: Remove the old wallpaper-scraper image if it exists
echo "[2/3] Removing old wallpaper-scraper image (if any)..."
docker rmi $(docker images --filter "reference=*wallpaper-scraper*" -q) 2>/dev/null || true
echo "  Done."

# Step 3: Build from scratch with no cache
echo "[3/3] Building wallpaper-scraper image (no cache)..."
echo ""
docker compose build --no-cache wallpaper-scraper

echo ""
echo "=== Build complete! Run with: docker compose up -d ==="
