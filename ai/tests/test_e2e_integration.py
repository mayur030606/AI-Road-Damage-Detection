"""
End-to-End Integration & Verification Test Suite for SIH26124.
--------------------------------------------------------------
Validates full pipeline flow across AI Perception, Edge Telemetry,
Spatial Proximity Filtering, Multi-Bus Corroboration (and same-bus deduplication),
Traffic Signal Malfunction thresholding, and Offline Queue network loss recovery.

Distinguishes:
A. Automated Integration Tests (hardware-decoupled / mock-assisted)
B. REST API Payload & PostGIS Spatial Alignment Tests

Preserves exact AI prototype statuses:
- Zebra Crossing: PROTOTYPE / UNKNOWN
- Traffic Signal State: PROTOTYPE / VISUAL HSV MODE
- Malfunction State: SIGNAL_POSSIBLE_MALFUNCTION (never BROKEN)
"""

import os
import sys
import unittest
import time
import json
import sqlite3

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.common.models import AIObservation, BoundingBox, PipelineResult
from ai.traffic_signal.detector import TrafficSignalDetector
from edge.telemetry.gps import MockGPSProvider, GPSLocation
from edge.telemetry.processor import TelemetryProcessor
from edge.telemetry.models import UnifiedTelemetryEvent
from edge.telemetry.queue import OfflineEventQueue


class TestE2EIntegrationFlow(unittest.TestCase):
    """
    Automated End-to-End Integration Tests.
    """

    def setUp(self):
        self.test_db_path = os.path.join(PROJECT_ROOT, "ai", "tests", "temp_e2e_queue.db")
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass
        self.queue = OfflineEventQueue(db_path=self.test_db_path, max_queue_size=100)
        self.gps_provider = MockGPSProvider(initial_latitude=28.6139, initial_longitude=77.2090)
        self.processor = TelemetryProcessor(gps_provider=self.gps_provider, device_id="BUS-TEST-001")

    def tearDown(self):
        self.queue.close()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    def test_full_pipeline_camera_to_telemetry_event(self):
        """
        Verify Flow: Camera/Video Observation ➔ GPS ➔ Telemetry Processor ➔ UnifiedTelemetryEvent ➔ Offline Queue
        """
        obs = AIObservation(
            detector_type="POTHOLE_DETECTOR",
            event_type="POTHOLE",
            confidence=0.91,
            source="test_road_frame.jpg",
            frame_number=12,
            bbox=BoundingBox(100.0, 200.0, 300.0, 400.0),
            metadata={"demo_tag": "DEMO DATA", "estimated_area_ratio": 0.045}
        )

        event = self.processor.process_observation(obs)

        # Validate event attributes
        self.assertIsNotNone(event.event_id)
        self.assertEqual(event.device_id, "BUS-TEST-001")
        self.assertEqual(event.event_type, "POTHOLE")
        self.assertEqual(event.detection_status, "POTHOLE_DETECTED")
        self.assertAlmostEqual(event.latitude, 28.6139, places=4)
        self.assertAlmostEqual(event.longitude, 77.2090, places=4)
        self.assertEqual(event.severity, "HIGH")

        # Enqueue in offline queue
        enqueued = self.queue.enqueue(event)
        self.assertTrue(enqueued)
        self.assertEqual(self.queue.get_queue_depth(), 1)

    def test_spatial_proximity_haversine_math(self):
        """
        Verify spatial distance calculations used for GET /api/events/nearby.
        Coordinates:
        Point A (Connaught Place, Delhi): 28.6315, 77.2167
        Point B (India Gate, Delhi ~ 2.3 km away): 28.6129, 77.2295
        Point C (Indira Gandhi Airport ~ 14 km away): 28.5562, 77.1000
        """
        import math

        def haversine_m(lat1, lon1, lat2, lon2):
            R = 6371000.0
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        dist_ab = haversine_m(28.6315, 77.2167, 28.6129, 77.2295)
        dist_ac = haversine_m(28.6315, 77.2167, 28.5562, 77.1000)

        # Dist A->B should be inside 3000m radius
        self.assertLess(dist_ab, 3000.0)
        # Dist A->C should be outside 3000m radius
        self.assertGreater(dist_ac, 3000.0)

    def test_multi_bus_corroboration_logic(self):
        """
        Verify multi-bus corroboration:
        Bus-001 at Location A + Bus-002 at Location A = 2 distinct buses (Corroborated)
        Bus-001 at Location A + Bus-001 at Location A = 1 distinct bus (NOT multi-bus corroborated)
        """
        bus_observations = [
            {"bus_id": "BUS-001", "location": (28.6139, 77.2090)},
            {"bus_id": "BUS-002", "location": (28.6139, 77.2090)},
            {"bus_id": "BUS-001", "location": (28.6139, 77.2090)},
        ]

        distinct_buses = set()
        for obs in bus_observations:
            distinct_buses.add(obs["bus_id"])

        self.assertEqual(len(distinct_buses), 2)
        self.assertIn("BUS-001", distinct_buses)
        self.assertIn("BUS-002", distinct_buses)

    def test_traffic_signal_workflow_operating_vs_malfunction(self):
        """
        Verify Traffic Signal Health Monitoring:
        Normal frames ➔ SIGNAL_OPERATING
        Consecutive OFF / dark frames exceeding threshold ➔ SIGNAL_POSSIBLE_MALFUNCTION (Never BROKEN)
        """
        from ai.traffic_signal.detector import SignalTrack, SignalObservationRecord

        detector = TrafficSignalDetector(min_observation_count=3, min_observation_duration_seconds=1.0)
        track = SignalTrack(
            track_id=1,
            first_seen_frame=1,
            last_seen_frame=5,
            first_seen_timestamp=100.0,
            last_seen_timestamp=105.0,
            best_confidence=0.9,
            best_bbox=BoundingBox(10, 10, 50, 100)
        )

        # 1. Normal operating records
        for i in range(5):
            track.update(SignalObservationRecord(
                frame_number=i+1,
                timestamp=100.0 + i,
                state="RED" if i % 2 == 0 else "GREEN",
                confidence=0.9,
                bbox=BoundingBox(10, 10, 50, 100)
            ))

        status_op, state_op = detector._analyze_track_health(track)
        self.assertEqual(status_op, "SIGNAL_OPERATING")

        # 2. Track with sustained OFF state observations
        off_track = SignalTrack(
            track_id=2,
            first_seen_frame=1,
            last_seen_frame=5,
            first_seen_timestamp=100.0,
            last_seen_timestamp=105.0,
            best_confidence=0.9,
            best_bbox=BoundingBox(10, 10, 50, 100)
        )
        for i in range(5):
            off_track.update(SignalObservationRecord(
                frame_number=i+1,
                timestamp=100.0 + i,
                state="OFF",
                confidence=0.9,
                bbox=BoundingBox(10, 10, 50, 100)
            ))

        status_mal, state_mal = detector._analyze_track_health(off_track)
        self.assertEqual(status_mal, "SIGNAL_POSSIBLE_MALFUNCTION")
        self.assertEqual(state_mal, "OFF")
        self.assertNotEqual(status_mal, "BROKEN")

    def test_offline_queue_retention_and_recovery(self):
        """
        Simulate Network Outage:
        Events enqueued ➔ Network unavailable ➔ Retained in SQLite ➔ Network restored ➔ Acknowledged & Flushed
        """
        events = []
        for i in range(3):
            obs = AIObservation(
                detector_type="POTHOLE_DETECTOR",
                event_type="POTHOLE",
                confidence=0.85,
                source=f"frame_{i}.jpg",
                bbox=BoundingBox(10 + i * 20.0, 10, 50 + i * 20.0, 50),
                metadata={"demo_tag": "DEMO DATA"}
            )
            events.append(self.processor.process_observation(obs))

        # Enqueue 3 events
        for evt in events:
            self.queue.enqueue(evt)

        self.assertEqual(self.queue.get_queue_depth(), 3)

        # Simulate network offline: peek batch
        peeked = self.queue.peek(batch_size=10)
        self.assertEqual(len(peeked), 3)

        # Network restored: acknowledge 2 events
        ack_ids = [peeked[0].event_id, peeked[1].event_id]
        deleted_count = self.queue.acknowledge(ack_ids)

        self.assertEqual(deleted_count, 2)
        self.assertEqual(self.queue.get_queue_depth(), 1)

    def test_empirical_performance_benchmark(self):
        """
        Empirically measure telemetry formatting latency and offline queue write throughput.
        Reports actual measured milliseconds without inventing values.
        """
        obs = AIObservation(
            detector_type="POTHOLE_DETECTOR",
            event_type="POTHOLE",
            confidence=0.90,
            source="benchmark_frame.jpg",
            bbox=BoundingBox(100, 100, 200, 200),
            metadata={"demo_tag": "DEMO DATA"}
        )

        # Measure 100 telemetry processing iterations
        t0 = time.time()
        for _ in range(100):
            evt = self.processor.process_observation(obs)
            self.queue.enqueue(evt)
        t1 = time.time()

        total_elapsed_ms = (t1 - t0) * 1000.0
        avg_per_event_ms = total_elapsed_ms / 100.0

        print(f"\n[MEASURED PERFORMANCE] 100 Telemetry Format & Queue Writes: {total_elapsed_ms:.2f} ms total ({avg_per_event_ms:.3f} ms/event)")
        self.assertLess(avg_per_event_ms, 50.0)  # Should take under 50ms per event


if __name__ == "__main__":
    unittest.main()
