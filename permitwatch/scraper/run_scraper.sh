#!/bin/bash
# run_scraper.sh
# ──────────────
# Full PermitWatch data pipeline for Intown Macon Neighborhood Association
#
# Usage:
#   ./run_scraper.sh              # default: 12 months
#   ./run_scraper.sh 6            # last 6 months
#   ./run_scraper.sh 12 --fresh   # re-scrape, ignore cache
#
# Cron example (run every Monday at 6am):
#   0 6 * * 1 cd /path/to/permitwatch && ./run_scraper.sh >> logs/scraper.log 2>&1

set -euo pipefail

MONTHS=${1:-12}
FRESH=${2:-""}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="logs"
DATA_DIR="data"

mkdir -p "$LOG_DIR" "$DATA_DIR"

echo "════════════════════════════════════════"
echo "  PermitWatch MBPZ Scraper"
echo "  $(date)"
echo "  Months back: $MONTHS"
echo "════════════════════════════════════════"

# Optional: clear geocode cache on --fresh run
if [ "$FRESH" = "--fresh" ]; then
  echo "[INFO] Clearing geocode cache..."
  rm -f geocode_cache.json
fi

# Step 1: Scrape mbpz.org
echo ""
echo "[STEP 1] Scraping MBPZ hearing pages..."
python3 mbpz_scraper.py \
  --months "$MONTHS" \
  --out "$DATA_DIR/mbpz_hearings_${TIMESTAMP}.json" \
  --pretty

# Copy to latest
cp "$DATA_DIR/mbpz_hearings_${TIMESTAMP}.json" "$DATA_DIR/mbpz_hearings_latest.json"
echo "[INFO] Raw data saved to $DATA_DIR/mbpz_hearings_latest.json"

# Step 2: Transform to PermitWatch format (with geocoding)
echo ""
echo "[STEP 2] Transforming to PermitWatch format + geocoding..."
python3 mbpz_to_permitwatch.py \
  --in  "$DATA_DIR/mbpz_hearings_latest.json" \
  --out "$DATA_DIR/permitwatch_data.json"

echo ""
echo "[STEP 3] Copying to app public directory..."
# Adjust this path to wherever your React app serves static files from
if [ -d "public" ]; then
  cp "$DATA_DIR/permitwatch_data.json" "public/permitwatch_data.json"
  echo "[INFO] Copied to public/permitwatch_data.json"
elif [ -d "src/data" ]; then
  cp "$DATA_DIR/permitwatch_data.json" "src/data/permitwatch_data.json"
  echo "[INFO] Copied to src/data/permitwatch_data.json"
else
  echo "[INFO] No public/ or src/data/ directory found — data stays in $DATA_DIR/"
fi

echo ""
echo "════════════════════════════════════════"
echo "  Pipeline complete!"
echo "  Output: $DATA_DIR/permitwatch_data.json"
echo "  $(date)"
echo "════════════════════════════════════════"
