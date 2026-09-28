"""
Unit test suite for DefectTracker and EventAggregator using ai.common.models.
"""

import unittest
from ai.common.models import BoundingBox, SingleDetection, ObservationEvent, PipelineResult, AIObservation
from ai.tracker import DefectTracker, TrackedDefect
from ai.aggregator import EventAggregator


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

    def test_multiple_distinct_defects_tracked(self):
        tracker = DefectTracker(iou_match_threshold=0.3, max_lost_frames=2)
        
        det1 = SingleDetection(class_id=0, class_name="pothole", confidence=0.9, bbox=BoundingBox(10, 10, 50, 50), area_ratio=0.01)
        det2 = SingleDetection(class_id=0, class_name="pothole", confidence=0.8, bbox=BoundingBox(300, 300, 350, 350), area_ratio=0.01)
        
        tracker.update([det1, det2], frame_idx=1)
        self.assertEqual(len(tracker.active_tracks), 2)
        
        closed = tracker.flush_remaining_tracks()
        self.assertEqual(len(closed), 2)


class TestEventAggregator(unittest.TestCase):

    def test_event_aggregation_from_track(self):
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

    def test_event_aggregation_from_pipeline_result(self):
        aggregator = EventAggregator(device_id="BUS-TEST-100")
        obs = AIObservation(
            detector_type="POTHOLE_DETECTOR",
            event_type="POTHOLE",
            confidence=0.89,
            source="frame_01.jpg",
            bbox=BoundingBox(20, 20, 80, 80),
            metadata={"estimated_area_ratio": 0.02}
        )
        res = PipelineResult(
            source="frame_01.jpg",
            image_width=640,
            image_height=480,
            observations=[obs]
        )

        events = aggregator.create_events_from_frame(res)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].defect_type, "POTHOLE")
        self.assertEqual(events[0].device_id, "BUS-TEST-100")


if __name__ == "__main__":
    unittest.main()
