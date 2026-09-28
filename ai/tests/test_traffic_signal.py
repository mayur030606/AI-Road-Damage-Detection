"""
Unit Test Suite for Traffic Signal Intelligence Subsystem.
"""

import unittest
import numpy as np
import cv2

from ai.common.models import BoundingBox, AIObservation
from ai.traffic_signal.detector import TrafficSignalDetector, SignalTrack, SignalObservationRecord
from ai.pipeline import AIPipeline


def create_synthetic_signal_image(width=640, height=480, state="RED") -> np.ndarray:
    """Generate synthetic road image containing a drawn traffic light housing with specified active lamp."""
    img = np.full((height, width, 3), 80, dtype=np.uint8)
    
    # Draw black vertical traffic light housing box
    box_x1, box_y1, box_x2, box_y2 = 280, 100, 360, 340
    cv2.rectangle(img, (box_x1, box_y1), (box_x2, box_y2), (20, 20, 20), -1)
    
    # Lamp centers
    red_center = (320, 140)
    yellow_center = (320, 220)
    green_center = (320, 300)
    radius = 25

    # Base dark lamps
    cv2.circle(img, red_center, radius, (10, 10, 50), -1)
    cv2.circle(img, yellow_center, radius, (10, 50, 50), -1)
    cv2.circle(img, green_center, radius, (10, 50, 10), -1)

    # Illuminate active state
    if state == "RED":
        cv2.circle(img, red_center, radius, (0, 0, 255), -1)
    elif state == "YELLOW":
        cv2.circle(img, yellow_center, radius, (0, 255, 255), -1)
    elif state == "GREEN":
        cv2.circle(img, green_center, radius, (0, 255, 0), -1)
    elif state == "OFF":
        # All lamps remain dark
        pass

    return img


class TestTrafficSignalDetector(unittest.TestCase):

    def setUp(self):
        self.detector = TrafficSignalDetector(
            model_path="yolov8n.pt",
            conf_threshold=0.25,
            min_observation_count=5,
            min_observation_duration_seconds=3.0,
            stuck_state_duration_seconds=15.0,
            device="cpu"
        )

    def test_state_recognition_red(self):
        img_red = create_synthetic_signal_image(state="RED")
        bbox = BoundingBox(280, 100, 360, 340)
        recognized_state = self.detector.recognize_signal_state(img_red, bbox)
        self.assertEqual(recognized_state, "RED")

    def test_state_recognition_yellow(self):
        img_yellow = create_synthetic_signal_image(state="YELLOW")
        bbox = BoundingBox(280, 100, 360, 340)
        recognized_state = self.detector.recognize_signal_state(img_yellow, bbox)
        self.assertEqual(recognized_state, "YELLOW")

    def test_state_recognition_green(self):
        img_green = create_synthetic_signal_image(state="GREEN")
        bbox = BoundingBox(280, 100, 360, 340)
        recognized_state = self.detector.recognize_signal_state(img_green, bbox)
        self.assertEqual(recognized_state, "GREEN")

    def test_state_recognition_off(self):
        img_off = create_synthetic_signal_image(state="OFF")
        # Extremely dark image
        dark_crop = np.full((100, 50, 3), 10, dtype=np.uint8)
        bbox = BoundingBox(0, 0, 50, 100)
        recognized_state = self.detector.recognize_signal_state(dark_crop, bbox)
        self.assertEqual(recognized_state, "OFF")

    def test_state_recognition_unknown(self):
        # Tiny 2x2 bounding box ROI
        tiny_img = np.zeros((10, 10, 3), dtype=np.uint8)
        bbox = BoundingBox(0, 0, 2, 2)
        recognized_state = self.detector.recognize_signal_state(tiny_img, bbox)
        self.assertEqual(recognized_state, "UNKNOWN")

    def test_insufficient_observations_no_malfunction(self):
        # Single frame observation should NEVER trigger malfunction
        rec = SignalObservationRecord(frame_number=1, timestamp=100.0, state="OFF", confidence=0.9, bbox=BoundingBox(10, 10, 50, 50))
        track = SignalTrack(track_id=1, first_seen_frame=1, last_seen_frame=1, first_seen_timestamp=100.0, last_seen_timestamp=100.0, best_confidence=0.9, best_bbox=BoundingBox(10, 10, 50, 50), observations=[rec])
        
        status, state = self.detector._analyze_track_health(track)
        self.assertNotEqual(status, "SIGNAL_POSSIBLE_MALFUNCTION")
        self.assertNotEqual(status, "BROKEN")

    def test_insufficient_duration_no_malfunction(self):
        # 5 observations within 1.0 second (< 3.0s min duration) should not trigger malfunction
        recs = [
            SignalObservationRecord(frame_number=i, timestamp=100.0 + i*0.1, state="OFF", confidence=0.9, bbox=BoundingBox(10, 10, 50, 50))
            for i in range(1, 6)
        ]
        track = SignalTrack(
            track_id=1,
            first_seen_frame=1,
            last_seen_frame=5,
            first_seen_timestamp=100.0,
            last_seen_timestamp=100.4,
            best_confidence=0.9,
            best_bbox=BoundingBox(10, 10, 50, 50),
            observations=recs
        )
        status, state = self.detector._analyze_track_health(track)
        self.assertNotEqual(status, "SIGNAL_POSSIBLE_MALFUNCTION")

    def test_repeated_off_possible_malfunction(self):
        # Sustained OFF state over 10 observations and 10.0 seconds
        recs = [
            SignalObservationRecord(frame_number=i, timestamp=100.0 + i*1.0, state="OFF", confidence=0.9, bbox=BoundingBox(10, 10, 50, 50))
            for i in range(1, 11)
        ]
        track = SignalTrack(
            track_id=1,
            first_seen_frame=1,
            last_seen_frame=10,
            first_seen_timestamp=100.0,
            last_seen_timestamp=110.0,
            best_confidence=0.9,
            best_bbox=BoundingBox(10, 10, 50, 50),
            observations=recs
        )
        status, state = self.detector._analyze_track_health(track)
        self.assertEqual(status, "SIGNAL_POSSIBLE_MALFUNCTION")
        self.assertEqual(state, "OFF")

    def test_stuck_state_possible_malfunction(self):
        # Stuck RED state over 20 observations and 20.0 seconds (>= 15.0s stuck threshold)
        recs = [
            SignalObservationRecord(frame_number=i, timestamp=100.0 + i*1.0, state="RED", confidence=0.9, bbox=BoundingBox(10, 10, 50, 50))
            for i in range(1, 21)
        ]
        track = SignalTrack(
            track_id=1,
            first_seen_frame=1,
            last_seen_frame=20,
            first_seen_timestamp=100.0,
            last_seen_timestamp=120.0,
            best_confidence=0.9,
            best_bbox=BoundingBox(10, 10, 50, 50),
            observations=recs
        )
        status, state = self.detector._analyze_track_health(track)
        self.assertEqual(status, "SIGNAL_POSSIBLE_MALFUNCTION")
        self.assertEqual(state, "RED")

    def test_normal_state_transitions_operating(self):
        # Normal state cycle RED -> GREEN -> YELLOW -> RED over 10 seconds
        states = ["RED", "RED", "GREEN", "GREEN", "GREEN", "YELLOW", "YELLOW", "RED", "RED", "GREEN"]
        recs = [
            SignalObservationRecord(frame_number=i+1, timestamp=100.0 + i*1.0, state=st, confidence=0.9, bbox=BoundingBox(10, 10, 50, 50))
            for i, st in enumerate(states)
        ]
        track = SignalTrack(
            track_id=1,
            first_seen_frame=1,
            last_seen_frame=10,
            first_seen_timestamp=100.0,
            last_seen_timestamp=109.0,
            best_confidence=0.9,
            best_bbox=BoundingBox(10, 10, 50, 50),
            observations=recs
        )
        status, state = self.detector._analyze_track_health(track)
        self.assertEqual(status, "SIGNAL_OPERATING")

    def test_prototype_mode_unvalidated_state_model(self):
        self.assertFalse(self.detector.has_validated_state_model)
        obs_list = self.detector.detect_frame(np.full((480, 640, 3), 80, dtype=np.uint8))
        self.assertIsInstance(obs_list, list)

    def test_pipeline_integration(self):
        pipeline = AIPipeline(run_pothole=False, run_zebra=False, run_traffic=False, run_traffic_signal=True)
        img = create_synthetic_signal_image(state="GREEN")
        res = pipeline.process_frame(img, source_name="test_signal_frame")
        self.assertIsNotNone(res)
        signal_obs = res.get_observations_by_detector("TRAFFIC_SIGNAL_DETECTOR")
        self.assertIsInstance(signal_obs, list)


if __name__ == "__main__":
    unittest.main()
