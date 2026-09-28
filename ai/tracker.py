"""
Temporal Object Tracker for Road Defects.

Tracks bounding boxes across video frames to assign persistent track IDs
to physical road defects as the bus moves.
"""

from dataclasses import dataclass, field
import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
from ai.common.models import BoundingBox, SingleDetection

logger = logging.getLogger("DefectTracker")


@dataclass
class TrackedDefect:
    """Represents a physical defect tracked across consecutive frames."""
    track_id: int
    class_id: int
    class_name: str
    first_seen_frame: int
    last_seen_frame: int
    best_confidence: float
    best_bbox: BoundingBox
    best_area_ratio: float
    total_frame_detections: int = 1
    status: str = "ACTIVE"  # "ACTIVE", "LOST", "COMPLETED"
    creation_timestamp: float = field(default_factory=time.time)

    def update(self, detection: SingleDetection, frame_idx: int):
        self.last_seen_frame = frame_idx
        self.total_frame_detections += 1
        
        # Keep track of highest confidence / largest bounding box observation
        if detection.confidence > self.best_confidence or detection.area_ratio > self.best_area_ratio:
            self.best_confidence = max(self.best_confidence, detection.confidence)
            if detection.area_ratio > self.best_area_ratio:
                self.best_bbox = detection.bbox
                self.best_area_ratio = detection.area_ratio


class DefectTracker:
    """Pure-Python Lightweight IoU Object Tracker."""

    def __init__(self, iou_match_threshold: float = 0.3, max_lost_frames: int = 5):
        """
        Args:
            iou_match_threshold: Minimum IoU to consider two bounding boxes as the same defect.
            max_lost_frames: Number of consecutive frames without detection before closing a track.
        """
        self.iou_match_threshold = iou_match_threshold
        self.max_lost_frames = max_lost_frames
        self.next_track_id = 1
        self.active_tracks: Dict[int, TrackedDefect] = {}
        self.completed_tracks: List[TrackedDefect] = []

    def update(self, detections: List[SingleDetection], frame_idx: int) -> List[TrackedDefect]:
        """
        Update tracker with new frame detections.

        Returns:
            List of newly completed/closed defect tracks in this frame.
        """
        matched_track_ids = set()
        unmatched_detections = list(detections)
        newly_closed_tracks: List[TrackedDefect] = []

        # 1. Match current detections to active tracks via IoU
        if self.active_tracks and unmatched_detections:
            active_ids = list(self.active_tracks.keys())
            
            for det in list(unmatched_detections):
                best_iou = 0.0
                best_track_id = None

                for track_id in active_ids:
                    if track_id in matched_track_ids:
                        continue
                    
                    track = self.active_tracks[track_id]
                    if track.class_id != det.class_id:
                        continue  # Must match class

                    iou = self._compute_iou(det.bbox, track.best_bbox)
                    if iou > best_iou and iou >= self.iou_match_threshold:
                        best_iou = iou
                        best_track_id = track_id

                if best_track_id is not None:
                    # Update existing track
                    self.active_tracks[best_track_id].update(det, frame_idx)
                    matched_track_ids.add(best_track_id)
                    unmatched_detections.remove(det)

        # 2. Create new tracks for unmatched detections
        for det in unmatched_detections:
            new_track = TrackedDefect(
                track_id=self.next_track_id,
                class_id=det.class_id,
                class_name=det.class_name,
                first_seen_frame=frame_idx,
                last_seen_frame=frame_idx,
                best_confidence=det.confidence,
                best_bbox=det.bbox,
                best_area_ratio=det.area_ratio,
            )
            self.active_tracks[self.next_track_id] = new_track
            self.next_track_id += 1

        # 3. Age out tracks not matched in recent frames
        for track_id in list(self.active_tracks.keys()):
            if track_id not in matched_track_ids:
                track = self.active_tracks[track_id]
                frames_lost = frame_idx - track.last_seen_frame
                if frames_lost > self.max_lost_frames:
                    track.status = "COMPLETED"
                    self.completed_tracks.append(track)
                    newly_closed_tracks.append(track)
                    del self.active_tracks[track_id]

        return newly_closed_tracks

    def flush_remaining_tracks(self) -> List[TrackedDefect]:
        """Close all remaining active tracks (call at end of video stream)."""
        closed = []
        for track_id, track in list(self.active_tracks.items()):
            track.status = "COMPLETED"
            self.completed_tracks.append(track)
            closed.append(track)
        self.active_tracks.clear()
        return closed

    @staticmethod
    def _compute_iou(boxA: BoundingBox, boxB: BoundingBox) -> float:
        """Calculate Intersection over Union (IoU) of two bounding boxes."""
        xA = max(boxA.x_min, boxB.x_min)
        yA = max(boxA.y_min, boxB.y_min)
        xB = min(boxA.x_max, boxB.x_max)
        yB = min(boxA.y_max, boxB.y_max)

        inter_area = max(0.0, xB - xA) * max(0.0, yB - yA)
        if inter_area == 0.0:
            return 0.0

        boxA_area = boxA.area_px
        boxB_area = boxB.area_px

        iou = inter_area / float(boxA_area + boxB_area - inter_area)
        return iou
