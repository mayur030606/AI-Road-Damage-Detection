"""
Automated Unit & Integration Test Suite for Phase 1 AI Pothole Detector Module.
"""

import os
import sys
import unittest
import numpy as np
import cv2

# Add root project path to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai.detector import BoundingBox, SingleDetection, FrameDetectionResult, PotholeDetector, DEFAULT_MODEL_PATH
from ai.tracker import DefectTracker, TrackedDefect
from ai.aggregator import EventAggregator, ObservationEvent


def create_synthetic_road_image(width=640, height=480, draw_pothole=True) -> np.ndarray:
    """Generate a synthetic asphalt road image with an optional drawn pothole."""
    img = np.full((height, width, 3), 60, dtype=np.uint8)
    noise = np.random.randint(-10, 10, (height, width, 3), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    if draw_pothole:
        center = (width // 2, height // 2)
        axes = (80, 50)
        cv2.ellipse(img, center, axes, 15, 0, 360, (20, 20, 20), -1)
        cv2.ellipse(img, center, axes, 15, 0, 360, (100, 100, 100), 3)

    return img


class TestBoundingBox(unittest.TestCase):
    def test_bbox_properties(self):
        bbox = BoundingBox(x_min=10.0, y_min=20.0, x_max=110.0, y_max=120.0)
        self.assertEqual(bbox.width, 100.0)
        self.assertEqual(bbox.height, 100.0)
        self.assertEqual(bbox.area_px, 10000.0)
        self.assertEqual(bbox.to_list(), [10.0, 20.0, 110.0, 120.0])


class TestPotholeDetectorValidation(unittest.TestCase):

    def test_rejection_of_generic_coco_model_remapping(self):
        """Verify that loading a generic COCO model (like yolov8n.pt with 80 classes) raises ValueError when require_pothole_class=True."""
        # Generic yolov8n.pt has 80 COCO classes (0: person, 1: bicycle, etc.)
        with self.assertRaises(ValueError) as ctx:
            PotholeDetector(model_path="yolov8n.pt", require_pothole_class=True)
        
        self.assertIn("generic COCO dataset model", str(ctx.exception))
        self.assertIn("Arbitrary class remapping", str(ctx.exception))

    def test_missing_model_file_raises_filenotfound(self):
        """Verify that non-existent model path raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            PotholeDetector(model_path="non_existent_weights_file.pt")

    def test_authentic_class_name_usage(self):
        """Verify that detector uses model.names directly without hardcoded overrides."""
        if os.path.exists(DEFAULT_MODEL_PATH):
            detector = PotholeDetector(model_path=DEFAULT_MODEL_PATH, require_pothole_class=True)
            self.assertEqual(detector.class_names, detector.model.names)
            # Ensure model is not generic COCO (80 classes)
            self.assertNotEqual(len(detector.class_names), 80, "Pothole model must not be generic 80-class COCO model")


class TestDefectTracker(unittest.TestCase):
    def test_temporal_tracking_deduplication(self):
        tracker = DefectTracker(iou_match_threshold=0.3, max_lost_frames=2)
        
        # Simulate 5 consecutive frames observing the same physical pothole
        for frame_idx in range(1, 6):
            bbox = BoundingBox(
                x_min=100.0 + frame_idx * 2,
                y_min=100.0 + frame_idx * 2,
                x_max=200.0 + frame_idx * 2,
                y_max=200.0 + frame_idx * 2
            )
            det = SingleDetection(
                class_id=0,
                class_name="pothole",
                confidence=0.85,
                bbox=bbox,
                area_ratio=0.03
            )
            tracker.update([det], frame_idx)

        closed_tracks = tracker.flush_remaining_tracks()
        self.assertEqual(len(closed_tracks), 1)
        track = closed_tracks[0]
        self.assertEqual(track.track_id, 1)
        self.assertEqual(track.class_name, "pothole")
        self.assertEqual(track.total_frame_detections, 5)


class TestEventAggregator(unittest.TestCase):
    def test_event_aggregation(self):
        aggregator = EventAggregator(device_id="BUS-TEST-99")
        track = TrackedDefect(
            track_id=42,
            class_id=0,
            class_name="pothole",
            first_seen_frame=1,
            last_seen_frame=10,
            best_confidence=0.92,
            best_bbox=BoundingBox(10, 10, 100, 100),
            best_area_ratio=0.05,
            total_frame_detections=10
        )

        event = aggregator.create_event_from_track(track)
        self.assertIsInstance(event, ObservationEvent)
        self.assertEqual(event.device_id, "BUS-TEST-99")
        self.assertEqual(event.defect_type, "POTHOLE")
        self.assertEqual(event.confidence, 0.92)


if __name__ == "__main__":
    unittest.main()
