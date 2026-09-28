"""
Edge Offline Event Queue & Deduplication System for SIH26124.

Buffers geo-tagged telemetry events locally during temporary network disconnection
and handles batching, acknowledgement, and spatial-temporal duplicate deduplication.
"""

from collections import deque
import datetime
import hashlib
import json
import logging
import os
import sqlite3
from typing import Dict, List, Optional, Tuple

from edge.telemetry.models import UnifiedTelemetryEvent

logger = logging.getLogger("OfflineEventQueue")


class OfflineEventQueue:
    """
    Persistent SQLite & Memory-backed Offline Event Queue for Bus Edge Units.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        max_queue_size: int = 10000,
        dedup_window_seconds: float = 5.0
    ):
        """
        Initialize OfflineEventQueue.

        Args:
            db_path: Path to SQLite DB file (defaults to ':memory:' for transient/testing).
            max_queue_size: Maximum pending events allowed in local queue.
            dedup_window_seconds: Time window for filtering duplicate telemetry events.
        """
        self.db_path = db_path
        self.max_queue_size = max_queue_size
        self.dedup_window_seconds = dedup_window_seconds

        # In-memory deduplication cache: fingerprint -> timestamp
        self._recent_fingerprints: Dict[str, float] = {}

        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite table structure."""
        cursor = self._conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_events (
                event_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detection_status TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def enqueue(self, event: UnifiedTelemetryEvent) -> bool:
        """
        Enqueue a telemetry event if not a spatial-temporal duplicate.

        Returns:
            True if enqueued successfully, False if rejected as duplicate or queue full.
        """
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

        # Check for duplicate
        if self.is_duplicate(event, current_timestamp=now_ts):
            logger.debug(f"Event [{event.event_id[:8]}] rejected as duplicate.")
            return False

        # Enforce maximum queue size limit
        if self.get_queue_depth() >= self.max_queue_size:
            logger.warning(f"Offline queue reached max limit of {self.max_queue_size}. Oldest event will be evicted.")
            self._evict_oldest()

        # Store in SQLite
        payload_json = event.to_json()
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO pending_events (event_id, device_id, event_type, detection_status, timestamp, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event.event_id, event.device_id, event.event_type, event.detection_status, event.timestamp, payload_json, now_ts)
        )
        self._conn.commit()

        # Record fingerprint for deduplication
        fp = self._compute_fingerprint(event)
        self._recent_fingerprints[fp] = now_ts

        logger.info(f"Enqueued event [{event.event_id[:8]}] (Type: {event.event_type}, Status: {event.detection_status})")
        return True

    def peek(self, batch_size: int = 50) -> List[UnifiedTelemetryEvent]:
        """
        Peek at oldest un-transmitted events without removing them from queue.
        """
        events: List[UnifiedTelemetryEvent] = []
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT payload_json FROM pending_events ORDER BY created_at ASC LIMIT ?",
            (batch_size,)
        )
        rows = cursor.fetchall()
        for row in rows:
            try:
                ev = UnifiedTelemetryEvent.from_json(row[0])
                events.append(ev)
            except Exception as e:
                logger.error(f"Failed to deserialize queued event JSON: {e}")

        return events

    def acknowledge(self, event_ids: List[str]) -> int:
        """
        Remove transmitted events from queue after successful server sync.

        Returns:
            Number of acknowledged events deleted.
        """
        if not event_ids:
            return 0

        cursor = self._conn.cursor()
        placeholders = ",".join(["?"] * len(event_ids))
        cursor.execute(
            f"DELETE FROM pending_events WHERE event_id IN ({placeholders})",
            event_ids
        )
        self._conn.commit()
        deleted_count = cursor.rowcount

        logger.info(f"Acknowledged and deleted {deleted_count} event(s) from offline queue.")
        return deleted_count

    def get_queue_depth(self) -> int:
        """Return total pending events in queue."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pending_events")
        return cursor.fetchone()[0]

    def clear(self):
        """Clear all pending events from queue."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM pending_events")
        self._conn.commit()
        self._recent_fingerprints.clear()

    def is_duplicate(self, event: UnifiedTelemetryEvent, current_timestamp: Optional[float] = None) -> bool:
        """
        Check if event is a spatial-temporal duplicate of a recently enqueued event.
        """
        now_ts = current_timestamp if current_timestamp is not None else datetime.datetime.now(datetime.timezone.utc).timestamp()
        
        # Cleanup expired fingerprints from cache
        expired = [fp for fp, ts in self._recent_fingerprints.items() if (now_ts - ts) > self.dedup_window_seconds]
        for fp in expired:
            del self._recent_fingerprints[fp]

        fp = self._compute_fingerprint(event)
        if fp in self._recent_fingerprints:
            last_seen_ts = self._recent_fingerprints[fp]
            if (now_ts - last_seen_ts) <= self.dedup_window_seconds:
                return True

        return False

    def _evict_oldest(self):
        """Evict oldest single event from database."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM pending_events WHERE event_id IN (SELECT event_id FROM pending_events ORDER BY created_at ASC LIMIT 1)")
        self._conn.commit()

    def close(self):
        """Close SQLite connection."""
        if hasattr(self, "_conn") and self._conn is not None:
            self._conn.close()

    @staticmethod
    def _compute_fingerprint(event: UnifiedTelemetryEvent) -> str:
        """
        Compute a unique fingerprint hash based on device, event_type, status, rounded bbox, and lat/lon.
        """
        lat_str = f"{event.latitude:.4f}" if event.latitude is not None else "NO_LAT"
        lon_str = f"{event.longitude:.4f}" if event.longitude is not None else "NO_LON"
        bbox_str = json.dumps([round(x, 1) for x in event.bounding_box]) if event.bounding_box else "NO_BBOX"

        raw_key = f"{event.device_id}:{event.event_type}:{event.detection_status}:{lat_str}:{lon_str}:{bbox_str}"
        return hashlib.md5(raw_key.encode("utf-8")).hexdigest()
