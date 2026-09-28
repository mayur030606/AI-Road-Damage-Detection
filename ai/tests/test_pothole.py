"""
Unit tests for Pothole Detector Module.
"""

import os
import unittest
import numpy as np
import cv2

from ai.pothole.detector import PotholeDetector, DEFAULT_POTHOLE_MODEL_PATH


def create_synthetic_road_image() -> np.ndarray:
    img = np.full((480, 640, 3), 60, dtype=np.uint8)
    # Dark ellipse representing pothole crater
    cv2.ellipse(img, (320, 240), (80, 50), 0, 0, 360, (20, 20, 20), -1)
    return img


class TestPotholeDetector(unittest.TestCase):

    def test_missing_model_file_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            PotholeDetector(model_path="non_existent_weights.pt")

    def test_generic_coco_model_rejection(self):
        """Verify that generic COCO 80-class models (like yolov8n.pt) are strictly rejected."""
        with self.assertRaises(ValueError) as ctx:
            PotholeDetector(model_path="yolov8n.pt", require_pothole_class=True)
        self.assertIn("generic COCO dataset model", str(ctx.exception))
        self.assertIn("Arbitrary class remapping", str(ctx.exception))

    def test_pothole_model_loading_and_class_names(self):
        if os.path.exists(DEFAULT_POTHOLE_MODEL_PATH):
            detector = PotholeDetector(model_path=DEFAULT_POTHOLE_MODEL_PATH, require_pothole_class=True)
            self.assertIsNotNone(detector.class_names)
            self.assertNotEqual(len(detector.class_names), 80, "Pothole model must not be generic 80-class COCO model")

    def test_confidence_threshold_setting(self):
        if os.path.exists(DEFAULT_POTHOLE_MODEL_PATH):
            detector = PotholeDetector(model_path=DEFAULT_POTHOLE_MODEL_PATH)
            detector.set_confidence_threshold(0.5)
            self.assertEqual(detector.conf_threshold, 0.5)

    def test_detect_frame_synthetic_image(self):
        if os.path.exists(DEFAULT_POTHOLE_MODEL_PATH):
            detector = PotholeDetector(model_path=DEFAULT_POTHOLE_MODEL_PATH)
            synthetic_img = create_synthetic_road_image()
            observations = detector.detect_frame(synthetic_img, source_name="test_road.jpg")
            self.assertIsInstance(observations, list)
            for obs in observations:
                self.assertEqual(obs.detector_type, "POTHOLE_DETECTOR")


if __name__ == "__main__":
    unittest.main()
