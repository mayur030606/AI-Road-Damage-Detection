"""
Unit tests for Zebra Crossing Detector Module.
"""

import unittest
import numpy as np

from ai.zebra_crossing.detector import ZebraCrossingDetector
from ai.common.models import AIObservation


class TestZebraCrossingDetector(unittest.TestCase):

    def test_prototype_mode_initialization(self):
        detector = ZebraCrossingDetector(model_path=None)
        self.assertFalse(detector.is_model_available)

    def test_prototype_detect_frame_output_structure(self):
        detector = ZebraCrossingDetector(model_path=None)
        img = np.full((480, 640, 3), 100, dtype=np.uint8)

        observations = detector.detect_frame(img, source_name="road_frame.jpg", frame_number=1)
        self.assertEqual(len(observations), 1)

        obs = observations[0]
        self.assertIsInstance(obs, AIObservation)
        self.assertEqual(obs.detector_type, "ZEBRA_CROSSING_DETECTOR")
        self.assertEqual(obs.event_type, "ZEBRA_CROSSING_UNKNOWN")
        self.assertEqual(obs.confidence, 0.0)
        self.assertEqual(obs.metadata["status"], "UNKNOWN")
        self.assertEqual(obs.metadata["implementation_status"], "PROTOTYPE")

    def test_unavailable_model_path_handling(self):
        detector = ZebraCrossingDetector(model_path="non_existent_zebra_model.pt")
        self.assertFalse(detector.is_model_available)


if __name__ == "__main__":
    unittest.main()
