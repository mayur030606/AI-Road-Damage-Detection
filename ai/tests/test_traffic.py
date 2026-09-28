"""
Unit tests for Traffic Density Estimator Module.
"""

import unittest
import numpy as np

from ai.traffic.density import TrafficDensityEstimator
from ai.common.models import AIObservation, BoundingBox


class TestTrafficDensityEstimator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.estimator = TrafficDensityEstimator(
            model_path="yolov8n.pt",
            conf_threshold=0.25,
            low_threshold=2,
            medium_threshold=6,
            device="cpu"
        )

    def test_authentic_model_class_names(self):
        self.assertIn(2, self.estimator.class_names)
        self.assertEqual(self.estimator.class_names[2], "car")
        self.assertIn("car", self.estimator.target_vehicle_classes)

    def test_empty_frame_yields_low_density(self):
        # Plain black frame with 0 vehicles
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        observations = self.estimator.estimate_density(img, source_name="empty_road.jpg")

        self.assertEqual(len(observations), 1)
        obs = observations[0]
        self.assertEqual(obs.detector_type, "TRAFFIC_DENSITY_ESTIMATOR")
        self.assertEqual(obs.event_type, "TRAFFIC_DENSITY_LOW")
        self.assertEqual(obs.metadata["density_level"], "LOW")
        self.assertEqual(obs.metadata["total_vehicles_detected"], 0)

    def test_density_classification_thresholds(self):
        # Low threshold: <= 2 vehicles -> LOW
        # Medium threshold: 3 to 6 vehicles -> MEDIUM
        # High threshold: > 6 vehicles -> HIGH
        self.assertEqual(self.estimator.low_threshold, 2)
        self.assertEqual(self.estimator.medium_threshold, 6)

    def test_roi_filtering_structure(self):
        roi = BoundingBox(x_min=100.0, y_min=100.0, x_max=500.0, y_max=400.0)
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        observations = self.estimator.estimate_density(img, roi_bbox=roi, source_name="roi_test.jpg")
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].bbox, roi)


if __name__ == "__main__":
    unittest.main()
