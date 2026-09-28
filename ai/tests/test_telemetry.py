"""
Unit Test Suite for Phase 3 GPS & Unified Event Telemetry Subsystem.
"""

import datetime
import json
import unittest

from ai.common.models import AIObservation, BoundingBox, PipelineResult
from edge.telemetry.gps import GPSLocation, MockGPSProvider, NMEAGPSProvider
from edge.telemetry.models import UnifiedTelemetryEvent
from edge.telemetry.processor import TelemetryProcessor
from edge.telemetry.queue import OfflineEventQueue


class TestGPSAbstraction(unittest.TestCase):

    def test_valid_gps_coordinates(self):
        loc = GPSLocation(latitude=18.5204, longitude=73.8567, fix_status="3D_FIX")
        self.assertTrue(loc.is_valid())
        self.assertEqual(loc.latitude, 18.5204)
        self.assertEqual(loc.longitude, 73.8567)

    def test_invalid_gps_coordinates(self):
        loc = GPSLocation(latitude=999.0, longitude=999.0, fix_status="INVALID")
        self.assertFalse(loc.is_valid())

    def test_missing_gps_fix(self):
        loc = GPSLocation(latitude=0.0, longitude=0.0, fix_status="NO_FIX")
        self.assertFalse(loc.is_valid())

    def test_stale_gps_timestamp(self):
        old_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=120)
        loc = GPSLocation(
            latitude=18.5204,
            longitude=73.8567,
            fix_status="STALE",
            timestamp=old_dt.isoformat()
        )
        self.assertFalse(loc.is_valid(max_age_seconds=30.0))

    def test_mock_gps_provider(self):
        mock = MockGPSProvider(initial_latitude=19.0760, initial_longitude=72.8777, fix_status="SIMULATED")
        loc = mock.get_location()
        self.assertTrue(loc.is_valid())
        self.assertEqual(loc.latitude, 19.0760)

        mock.set_no_fix()
        loc_no_fix = mock.get_location()
        self.assertFalse(loc_no_fix.is_valid())
        self.assertEqual(loc_no_fix.fix_status, "NO_FIX")

    def test_nmea_gps_provider_parser(self):
        nmea_provider = NMEAGPSProvider()
        sentence = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
        loc = nmea_provider.parse_nmea_sentence(sentence)
        self.assertIsNotNone(loc)
        self.assertTrue(loc.is_valid())
        self.assertAlmostEqual(loc.latitude, 48.1173, places=3)
        self.assertAlmostEqual(loc.longitude, 11.5166, places=3)


class TestUnifiedTelemetryEventSerialization(unittest.TestCase):

    def test_event_serialization_roundtrip(self):
        event = UnifiedTelemetryEvent(
            device_id="BUS-TEST-101",
            event_type="POTHOLE",
            detection_status="POTHOLE_DETECTED",
            confidence=0.92,
            latitude=18.5204,
            longitude=73.8567,
            gps_fix_status="3D_FIX",
            bounding_box=[10.0, 20.0, 100.0, 120.0],
            severity="HIGH",
            source="road_video.mp4",
            metadata={"estimated_area_sqm": 0.45}
        )

        json_str = event.to_json()
        deserialized = UnifiedTelemetryEvent.from_json(json_str)

        self.assertEqual(deserialized.event_id, event.event_id)
        self.assertEqual(deserialized.device_id, "BUS-TEST-101")
        self.assertEqual(deserialized.event_type, "POTHOLE")
        self.assertEqual(deserialized.latitude, 18.5204)
        self.assertEqual(deserialized.longitude, 73.8567)
        self.assertEqual(deserialized.severity, "HIGH")


class TestTelemetryProcessor(unittest.TestCase):

    def setUp(self):
        self.mock_gps = MockGPSProvider(initial_latitude=18.5204, initial_longitude=73.8567)
        self.processor = TelemetryProcessor(gps_provider=self.mock_gps, device_id="BUS-999")

    def test_unified_events_for_all_four_ai_capabilities(self):
        # 1. Pothole Observation
        obs_pothole = AIObservation(
            detector_type="POTHOLE_DETECTOR",
            event_type="POTHOLE",
            confidence=0.88,
            source="frame_01.jpg",
            bbox=BoundingBox(10, 10, 50, 50),
            metadata={"estimated_area_ratio": 0.05}
        )

        # 2. Zebra Crossing Observation
        obs_zebra = AIObservation(
            detector_type="ZEBRA_CROSSING_DETECTOR",
            event_type="ZEBRA_CROSSING_UNKNOWN",
            confidence=0.0,
            source="frame_01.jpg",
            metadata={"status": "UNKNOWN"}
        )

        # 3. Traffic Density Observation
        obs_traffic = AIObservation(
            detector_type="TRAFFIC_DENSITY_ESTIMATOR",
            event_type="TRAFFIC_DENSITY_MEDIUM",
            confidence=0.80,
            source="frame_01.jpg",
            metadata={"density_level": "MEDIUM", "total_vehicles_detected": 4}
        )

        # 4. Traffic Signal Observation
        obs_signal = AIObservation(
            detector_type="TRAFFIC_SIGNAL_DETECTOR",
            event_type="TRAFFIC_SIGNAL",
            confidence=0.91,
            source="frame_01.jpg",
            bbox=BoundingBox(100, 100, 140, 200),
            metadata={"status": "SIGNAL_POSSIBLE_MALFUNCTION", "signal_state": "OFF"}
        )

        pipeline_result = PipelineResult(
            source="frame_01.jpg",
            image_width=640,
            image_height=480,
            observations=[obs_pothole, obs_zebra, obs_traffic, obs_signal]
        )

        events = self.processor.process_pipeline_result(pipeline_result)
        self.assertEqual(len(events), 4)

        event_types = [ev.event_type for ev in events]
        self.assertIn("POTHOLE", event_types)
        self.assertIn("ZEBRA_CROSSING", event_types)
        self.assertIn("TRAFFIC_DENSITY", event_types)
        self.assertIn("TRAFFIC_SIGNAL", event_types)

        # Check severity derivations
        signal_event = next(ev for ev in events if ev.event_type == "TRAFFIC_SIGNAL")
        self.assertEqual(signal_event.severity, "CRITICAL")

        pothole_event = next(ev for ev in events if ev.event_type == "POTHOLE")
        self.assertEqual(pothole_event.severity, "HIGH")

    def test_missing_and_invalid_gps_graceful_handling(self):
        # Set invalid GPS
        self.mock_gps.set_invalid_coordinates()
        obs = AIObservation(
            detector_type="POTHOLE_DETECTOR",
            event_type="POTHOLE",
            confidence=0.85,
            source="frame_01.jpg",
            bbox=BoundingBox(10, 10, 50, 50)
        )

        event = self.processor.process_observation(obs)
        self.assertIsNone(event.latitude)
        self.assertIsNone(event.longitude)
        self.assertEqual(event.gps_fix_status, "INVALID")
        self.assertIn("gps_warning", event.metadata)


class TestOfflineEventQueueAndDeduplication(unittest.TestCase):

    def setUp(self):
        self.queue = OfflineEventQueue(db_path=":memory:", dedup_window_seconds=5.0)

    def tearDown(self):
        if hasattr(self, "queue") and self.queue is not None:
            self.queue.close()

    def test_enqueue_peek_acknowledge(self):
        ev1 = UnifiedTelemetryEvent(device_id="BUS-1", event_type="POTHOLE", confidence=0.9, bounding_box=[10.0, 10.0, 50.0, 50.0])
        ev2 = UnifiedTelemetryEvent(device_id="BUS-1", event_type="TRAFFIC_DENSITY", confidence=0.8, bounding_box=[200.0, 200.0, 300.0, 300.0])

        self.assertTrue(self.queue.enqueue(ev1))
        self.assertTrue(self.queue.enqueue(ev2))

        self.assertEqual(self.queue.get_queue_depth(), 2)

        peeked = self.queue.peek(batch_size=10)
        self.assertEqual(len(peeked), 2)

        ack_count = self.queue.acknowledge([ev1.event_id])
        self.assertEqual(ack_count, 1)
        self.assertEqual(self.queue.get_queue_depth(), 1)

    def test_duplicate_event_deduplication(self):
        ev = UnifiedTelemetryEvent(
            device_id="BUS-DEDUP",
            event_type="POTHOLE",
            detection_status="POTHOLE_DETECTED",
            latitude=18.5204,
            longitude=73.8567,
            bounding_box=[10.0, 10.0, 50.0, 50.0]
        )

        # First enqueue succeeds
        self.assertTrue(self.queue.enqueue(ev))

        # Immediate duplicate enqueue fails
        ev_dup = UnifiedTelemetryEvent(
            device_id="BUS-DEDUP",
            event_type="POTHOLE",
            detection_status="POTHOLE_DETECTED",
            latitude=18.5204,
            longitude=73.8567,
            bounding_box=[10.0, 10.0, 50.0, 50.0]
        )
        self.assertFalse(self.queue.enqueue(ev_dup))
        self.assertEqual(self.queue.get_queue_depth(), 1)


if __name__ == "__main__":
    unittest.main()
