"""
Automated Local Storage Cleanup Routine for SIH26124 Edge Node.

Deletes local .mp4 video incident captures from ai/video_captures/ that:
1. Are older than 7 days (retention threshold).
2. Have been verified as SYNCED in the offline SQLite queue.
"""

import datetime
import logging
import os
import sqlite3
import sys
import time

CAPTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai", "video_captures"))
LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai", "logs", "cleanup.log"))
QUEUE_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai", "queue", "incidents_queue.db"))
RETENTION_SECONDS = 7 * 24 * 60 * 60  # 7 days

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("StorageCleanup")


def get_synced_video_files() -> set:
    """Query SQLite queue for video paths marked as SYNCED."""
    if not os.path.exists(QUEUE_DB):
        return set()
    try:
        conn = sqlite3.connect(QUEUE_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT video_clip_path FROM incidents_queue WHERE status = 'SYNCED'")
        rows = cursor.fetchall()
        conn.close()
        return {os.path.normpath(r[0]) for r in rows if r[0]}
    except Exception as e:
        logger.warning(f"Could not read SQLite queue: {e}")
        return set()


def run_cleanup():
    logger.info(f"Starting 24-hour storage cleanup routine. Target: '{CAPTURES_DIR}' (Retention: 7 days)...")

    if not os.path.exists(CAPTURES_DIR):
        logger.info("Captures directory does not exist yet. Nothing to clean.")
        return

    now = time.time()
    synced_files = get_synced_video_files()
    purged_count = 0
    reclaimed_bytes = 0

    for fname in os.listdir(CAPTURES_DIR):
        if not fname.endswith(".mp4"):
            continue

        fpath = os.path.join(CAPTURES_DIR, fname)
        if not os.path.isfile(fpath):
            continue

        file_age = now - os.path.getmtime(fpath)
        file_size = os.path.getsize(fpath)

        # Condition: Older than 7 days OR (older than 3 days AND verified synced)
        is_older_than_7_days = file_age >= RETENTION_SECONDS
        is_synced_and_older_than_3_days = (file_age >= 3 * 86400) and (os.path.normpath(fpath) in synced_files)

        if is_older_than_7_days or is_synced_and_older_than_3_days:
            try:
                os.remove(fpath)
                purged_count += 1
                reclaimed_bytes += file_size
                logger.info(f"Purged: '{fname}' (Age: {file_age / 86400:.1f} days, Size: {file_size / (1024*1024):.2f} MB)")
            except Exception as e:
                logger.error(f"Failed to delete '{fpath}': {e}")

    logger.info(f"Cleanup complete. Removed {purged_count} files, reclaimed {reclaimed_bytes / (1024*1024):.2f} MB.")


if __name__ == "__main__":
    run_cleanup()
