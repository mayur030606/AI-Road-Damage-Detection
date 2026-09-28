"""
Unit & Integration Tests for Unified Real-Time Road Intelligence Video Pipeline.
"""

import os
import sys
import unittest
import numpy as np
import cv2

# Add root project path to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai.road_intelligence import UnifiedRoadIntelligencePipeline, VideoPipelineSummary, PerformanceMetrics
from ai.pothole.downloader import DEFAULT_POTHOLE_MODEL_PATH


def create_temp_test_video(filename="temp_test_video.mp4", num_frames=10, width=640, height=480, fps=15):
    """Helper to create a temporary MP4 video file for testing."""
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    for i in range(num_frames):
        img = np.full((height, width, 3), 50 + i * 2, dtype=np.uint8)
        out.write(img)
    out.release()
    return filename


class TestRoadIntelligencePipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_video_path = create_temp_test_video(num_frames=10)
        cls.pipeline = UnifiedRoadIntelligencePipeline(
            pothole_model_path=DEFAULT_POTHOLE_MODEL_PATH,
            vehicle_model_path="yolov8n.pt",
            pothole_conf=0.25,
            traffic_conf=0.25,
            device="cpu"
        )

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_video_path):
            os.remove(cls.test_video_path)
        out_v = "temp_test_out.mp4"
        if os.path.exists(out_v):
            os.remove(out_v)
        out_j = "temp_test_out.json"
        if os.path.exists(out_j):
            os.remove(out_j)

    def test_pipeline_initialization(self):
        self.assertIsNotNone(self.pipeline.perception_pipeline)
        self.assertIsNotNone(self.pipeline.event_aggregator)

    def test_invalid_video_path_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            self.pipeline.process_video(video_path="non_existent_video_12345.mp4")

    def test_max_frames_limit_enforced(self):
        summary = self.pipeline.process_video(
            video_path=self.test_video_path,
            max_frames=3
        )
        self.assertIsInstance(summary, VideoPipelineSummary)
        self.assertEqual(summary.performance.processed_frames, 3)

    def test_unified_result_serialization(self):
        summary = self.pipeline.process_video(
            video_path=self.test_video_path,
            output_json_path="temp_test_out.json",
            max_frames=2
        )
        json_str = summary.to_json()
        self.assertIn("performance_metrics", json_str)
        self.assertIn("pothole_summary", json_str)
        self.assertIn("traffic_summary", json_str)
        self.assertIn("zebra_summary", json_str)
        self.assertTrue(os.path.exists("temp_test_out.json"))

    def test_modules_integration(self):
        summary = self.pipeline.process_video(
            video_path=self.test_video_path,
            max_frames=2
        )
        self.assertEqual(summary.zebra_crossing_status, "PROTOTYPE / UNKNOWN")
        self.assertIn("LOW", summary.traffic_density_distribution)


if __name__ == "__main__":
    unittest.main()
