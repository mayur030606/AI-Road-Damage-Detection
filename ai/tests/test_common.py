"""
Unit tests for Common Data Models (BoundingBox, AIObservation, PipelineResult).
"""

import unittest
import json
from ai.common.models import BoundingBox, AIObservation, PipelineResult


class TestCommonModels(unittest.TestCase):

    def test_bounding_box_calculations(self):
        bbox = BoundingBox(x_min=10.0, y_min=20.0, x_max=110.0, y_max=120.0)
        self.assertEqual(bbox.width, 100.0)
        self.assertEqual(bbox.height, 100.0)
        self.assertEqual(bbox.area_px, 10000.0)
        self.assertEqual(bbox.to_list(), [10.0, 20.0, 110.0, 120.0])
        
        bbox_dict = bbox.to_dict()
        self.assertEqual(bbox_dict["width"], 100.0)
        self.assertEqual(bbox_dict["area_px"], 10000.0)

    def test_ai_observation_serialization(self):
        bbox = BoundingBox(x_min=50.0, y_min=50.0, x_max=150.0, y_max=150.0)
        obs = AIObservation(
            detector_type="POTHOLE_DETECTOR",
            event_type="POTHOLE",
            confidence=0.885,
            source="road_test.jpg",
            frame_number=12,
            bbox=bbox,
            metadata={"estimated_area_sqm": 0.42}
        )

        obs_dict = obs.to_dict()
        self.assertEqual(obs_dict["detector_type"], "POTHOLE_DETECTOR")
        self.assertEqual(obs_dict["event_type"], "POTHOLE")
        self.assertEqual(obs_dict["confidence"], 0.885)
        self.assertEqual(obs_dict["frame_number"], 12)
        self.assertEqual(obs_dict["bbox"], [50.0, 50.0, 150.0, 150.0])

        json_str = obs.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["detector_type"], "POTHOLE_DETECTOR")
        self.assertEqual(parsed["source"], "road_test.jpg")

    def test_pipeline_result_aggregation(self):
        obs1 = AIObservation(
            detector_type="POTHOLE_DETECTOR",
            event_type="POTHOLE",
            confidence=0.9,
            source="frame_01.jpg"
        )
        obs2 = AIObservation(
            detector_type="TRAFFIC_DENSITY_ESTIMATOR",
            event_type="TRAFFIC_DENSITY_LOW",
            confidence=1.0,
            source="frame_01.jpg",
            metadata={"density_level": "LOW", "total_vehicles_detected": 1}
        )

        res = PipelineResult(
            source="frame_01.jpg",
            image_width=640,
            image_height=480,
            observations=[obs1, obs2],
            inference_time_ms=12.5
        )

        self.assertEqual(res.total_observations, 2)
        potholes = res.get_observations_by_detector("POTHOLE_DETECTOR")
        self.assertEqual(len(potholes), 1)

        res_dict = res.to_dict()
        self.assertEqual(res_dict["total_observations"], 2)
        self.assertEqual(res_dict["image_dimensions"], {"width": 640, "height": 480})


if __name__ == "__main__":
    unittest.main()
