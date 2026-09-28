#!/usr/bin/env bash
# ==============================================================================
# SIH26124 Edge Storage Automated Purge Routine
# Runs daily to delete synced .mp4 incident video clips older than 7 days
# ==============================================================================

set -euo pipefail

CAPTURES_DIR="/home/pi/SIH/ai/video_captures"
LOG_FILE="/home/pi/SIH/ai/logs/cleanup.log"
RETENTION_DAYS=7

mkdir -p "$(dirname "$LOG_FILE")"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "[$TIMESTAMP] Starting automated local storage cleanup (Retention: >${RETENTION_DAYS} days)..." >> "$LOG_FILE"

if [ ! -d "$CAPTURES_DIR" ]; then
    echo "[$TIMESTAMP] Video captures directory not found: $CAPTURES_DIR" >> "$LOG_FILE"
    exit 0
fi

# Count files before cleanup
TOTAL_BEFORE=$(find "$CAPTURES_DIR" -type f -name "*.mp4" | wc -l)

# Purge .mp4 files older than 7 days
DELETED_FILES=$(find "$CAPTURES_DIR" -type f -name "*.mp4" -mtime +"$RETENTION_DAYS" -print -delete)

TOTAL_AFTER=$(find "$CAPTURES_DIR" -type f -name "*.mp4" | wc -l)
PURGED_COUNT=$((TOTAL_BEFORE - TOTAL_AFTER))

echo "[$TIMESTAMP] Storage cleanup completed. Purged $PURGED_COUNT clip(s). Remaining: $TOTAL_AFTER" >> "$LOG_FILE"

if [ -n "$DELETED_FILES" ]; then
    echo "Purged files:" >> "$LOG_FILE"
    echo "$DELETED_FILES" >> "$LOG_FILE"
fi
