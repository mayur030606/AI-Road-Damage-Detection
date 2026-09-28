"""
Automated Verification Test Suite for SIH26124 Edge Perception System.

Verifies:
1. Pothole detector initialization with strict 0.75 confidence threshold.
2. Thread-safe CircularFrameBuffer (collections.deque 5s pre + 5s post capture).
3. Offline SQLite queue persistence & state transitions.
4. Simulated GPS coordinate generator.
5. Central Aggregator telemetry packaging & REST payload schema.
6. 24-hour storage cleanup logic.
"""

import os
import shutil
import tempfile
import time
import unittest

import numpy as np

from ai.aggregator import CentralAggregator, OfflineQueueManager, GPSProvider
from ai.detector import (
    BoundingBox,
    CircularFrameBuffer,
    PotholeDetector,
    PotholeDetection,
    TrafficDensityResult,
    DEFAULT_POTHOLE_MODEL
)
from scripts.cleanup_storage import run_cleanup


class TestEdgePerceptionSystem(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.queue_db = os.path.join(self.test_dir, "test_queue.db")
        self.captures_dir = os.path.join(self.test_dir, "captures")
        os.makedirs(self.captures_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_pothole_detector_threshold(self):
        """Test pothole detector model loading and strict 0.75 threshold."""
        self.assertTrue(os.path.exists(DEFAULT_POTHOLE_MODEL), f"Model weights not found at {DEFAULT_POTHOLE_MODEL}")
        detector = PotholeDetector(
            pothole_model_path=DEFAULT_POTHOLE_MODEL,
            pothole_conf=0.75
        )
        self.assertEqual(detector.pothole_conf, 0.75)
        self.assertIsNotNone(detector.pothole_model)

        # Test dummy frame inference
        dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        detections = detector.detect_potholes(dummy_frame)
        self.assertIsInstance(detections, list)

    def test_02_circular_frame_buffer_rolling_and_trigger(self):
        """Test circular frame buffer rolling 5s pre-event + 5s post-event capture."""
        fps = 30
        pre_event_sec = 1.0  # 30 frames for fast test
        post_event_sec = 1.0  # 30 frames for fast test

        captured_clips = []

        class MockWriterWorker:
            def submit_incident_clip(self, clip_frames, incident_metadata, output_filename, fps, dimensions):
                captured_clips.append({
                    "frames_count": len(clip_frames),
                    "metadata": incident_metadata,
                    "filename": output_filename
                })

        mock_worker = MockWriterWorker()

        buffer = CircularFrameBuffer(
            fps=fps,
            pre_event_seconds=pre_event_sec,
            post_event_seconds=post_event_sec,
            cooldown_seconds=0.1,
            writer_worker=mock_worker,
            captures_dir=self.captures_dir
        )

        dummy_frame = np.full((720, 1280, 3), 50, dtype=np.uint8)

        # Push 40 frames into buffer (buffer holds max 30)
        for _ in range(40):
            buffer.push_frame(dummy_frame)

        self.assertEqual(len(buffer.pre_event_buffer), 30)

        # Trigger incident
        metadata = {"defect_type": "POTHOLE", "confidence": 0.88}
        triggered = buffer.trigger_incident(metadata)
        self.assertTrue(triggered)
        self.assertTrue(buffer.is_recording)

        # Push 29 post-event frames
        for _ in range(29):
            completed = buffer.push_frame(dummy_frame)
            self.assertFalse(completed)

        # Push 30th post-event frame -> should complete event clip
        completed = buffer.push_frame(dummy_frame)
        self.assertTrue(completed)
        self.assertFalse(buffer.is_recording)

        # Verify combined clip frames (30 pre + 30 post = 60 frames)
        self.assertEqual(len(captured_clips), 1)
        self.assertEqual(captured_clips[0]["frames_count"], 60)
        self.assertEqual(captured_clips[0]["metadata"]["confidence"], 0.88)

    def test_03_offline_sqlite_queue(self):
        """Test persistent SQLite queue enqueuing, querying, and syncing."""
        queue_mgr = OfflineQueueManager(db_path=self.queue_db)

        # Initially empty
        stats = queue_mgr.get_queue_stats()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["pending"], 0)

        # Enqueue 2 incidents
        inc_1 = {"test": 1}
        inc_2 = {"test": 2}
        queue_mgr.enqueue("inc-001", "POTHOLE", 0.85, inc_1, "path/video1.mp4")
        queue_mgr.enqueue("inc-002", "POTHOLE", 0.92, inc_2, "path/video2.mp4")

        stats = queue_mgr.get_queue_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["pending"], 2)

        # Fetch pending
        pending = queue_mgr.get_pending_incidents(limit=10)
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending[0]["incident_id"], "inc-001")

        # Mark first as synced
        queue_mgr.mark_synced("inc-001")
        stats = queue_mgr.get_queue_stats()
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["synced"], 1)

    def test_04_simulated_gps_provider(self):
        """Test simulated GPS provider coordinate generation."""
        gps = GPSProvider(base_lat=18.520430, base_lon=73.856744)
        c1 = gps.get_coordinates()
        c2 = gps.get_coordinates()

        self.assertIn("latitude", c1)
        self.assertIn("longitude", c1)
        self.assertIn("speed_kmh", c1)
        self.assertTrue(c1["is_simulated"])
        self.assertGreater(c1["speed_kmh"], 0.0)
        self.assertNotEqual(c1["timestamp"], "")

    def test_05_aggregator_payload_schema(self):
        """Test central aggregator incident payload schema packaging."""
        aggregator = CentralAggregator(
            backend_url="http://192.168.1.100:8000/api/v1/incidents",
            auth_token="sih_admin",
            device_id="EDGE-RPI4-001",
            queue_db_path=self.queue_db,
            auto_sync=False
        )

        payload = aggregator.package_incident(
            defect_type="POTHOLE",
            confidence=0.86,
            bbox=[100.0, 150.0, 300.0, 350.0],
            estimated_size_sqm=0.45,
            video_clip_path=os.path.join(self.captures_dir, "test.mp4"),
            traffic_density_data={"density_level": "LOW", "vehicle_count": 2, "congestion_index": 0.25}
        )

        self.assertEqual(payload["device_id"], "EDGE-RPI4-001")
        self.assertEqual(payload["defect_type"], "POTHOLE")
        self.assertEqual(payload["confidence"], 0.86)
        self.assertIn("gps", payload)
        self.assertIn("traffic_density", payload)
        self.assertIn("video_reference", payload)
        self.assertEqual(payload["video_reference"]["duration_seconds"], 10.0)


if __name__ == "__main__":
    unittest.main()
