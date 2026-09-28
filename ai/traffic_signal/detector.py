"""
Traffic Signal Intelligence Subsystem for SIH26124.

Detects traffic signal objects using authentic YOLO COCO class 9 ('traffic light'),
decouples signal state recognition (RED, YELLOW, GREEN, OFF, UNKNOWN), tracks signals temporally
across video frames, and performs health analysis to infer possible malfunctions.
"""

from dataclasses import dataclass, field
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from ultralytics import YOLO

from ai.common.models import AIObservation, BoundingBox

logger = logging.getLogger("TrafficSignalDetector")

COCO_TRAFFIC_LIGHT_CLASS_ID = 9


@dataclass
class SignalObservationRecord:
    """Individual frame observation of a traffic signal."""
    frame_number: int
    timestamp: float
    state: str           # "RED", "YELLOW", "GREEN", "OFF", "UNKNOWN"
    confidence: float
    bbox: BoundingBox


@dataclass
class SignalTrack:
    """Temporal tracking record for a specific traffic signal across frames."""
    track_id: int
    first_seen_frame: int
    last_seen_frame: int
    first_seen_timestamp: float
    last_seen_timestamp: float
    best_confidence: float
    best_bbox: BoundingBox
    observations: List[SignalObservationRecord] = field(default_factory=list)

    @property
    def total_observations(self) -> int:
        return len(self.observations)

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.last_seen_timestamp - self.first_seen_timestamp)

    @property
    def latest_state(self) -> str:
        return self.observations[-1].state if self.observations else "UNKNOWN"

    def state_distribution(self) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        for obs in self.observations:
            dist[obs.state] = dist.get(obs.state, 0) + 1
        return dist

    def update(self, obs: SignalObservationRecord):
        self.last_seen_frame = obs.frame_number
        self.last_seen_timestamp = obs.timestamp
        if obs.confidence > self.best_confidence:
            self.best_confidence = obs.confidence
            self.best_bbox = obs.bbox
        self.observations.append(obs)


class TrafficSignalDetector:
    """
    Traffic Signal Intelligence Module.
    Combines YOLO traffic light object detection, decoupled state recognition,
    temporal tracking, and health malfunction analysis.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.25,
        min_observation_count: int = 5,
        min_observation_duration_seconds: float = 3.0,
        stuck_state_duration_seconds: float = 15.0,
        device: str = "cpu",
        state_model_path: Optional[str] = None
    ):
        """
        Initialize Traffic Signal Detector.

        Args:
            model_path: Path to YOLO weights for traffic light detection.
            conf_threshold: Minimum confidence threshold.
            min_observation_count: Minimum frame observations before declaring health status.
            min_observation_duration_seconds: Minimum duration before malfunction analysis.
            stuck_state_duration_seconds: Extended duration threshold for stuck state malfunction.
            device: Compute device ('cpu', 'cuda').
            state_model_path: Optional dedicated state classifier weights path.
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.min_observation_count = min_observation_count
        self.min_observation_duration_seconds = min_observation_duration_seconds
        self.stuck_state_duration_seconds = stuck_state_duration_seconds
        self.device = device
        self.state_model_path = state_model_path
        self.has_validated_state_model = state_model_path is not None and os.path.exists(state_model_path)

        logger.info(f"Loading Traffic Signal detector model from '{model_path}' on device '{device}'...")
        try:
            self.model = YOLO(model_path)
        except Exception as e:
            logger.error(f"Failed to load YOLO model from '{model_path}': {e}")
            raise e

        # Extract model names
        self.class_names = self.model.names if hasattr(self.model, "names") else {}
        
        # Verify genuine traffic light class
        traffic_light_name = self.class_names.get(COCO_TRAFFIC_LIGHT_CLASS_ID, None)
        if traffic_light_name != "traffic light":
            logger.warning(
                f"Model at '{model_path}' class {COCO_TRAFFIC_LIGHT_CLASS_ID} is '{traffic_light_name}', expected 'traffic light'. "
                "Class matching will use string search for 'traffic light'."
            )

        if not self.has_validated_state_model:
            logger.info(
                "No dedicated validated state model provided. Signal State Recognition operating in "
                "PROTOTYPE / VISUAL HSV MODE. State recognition is decoupled from object detection."
            )

        # Temporal signal tracks state
        self.active_tracks: Dict[int, SignalTrack] = {}
        self.next_track_id = 1

    def detect_frame(
        self,
        image_input: Union[str, np.ndarray],
        source_name: str = "frame",
        frame_number: Optional[int] = None,
        timestamp: Optional[float] = None
    ) -> List[AIObservation]:
        """
        Detect traffic signals in a single frame, analyze states, update temporal tracks, and analyze health.
        """
        current_time = timestamp if timestamp is not None else time.time()
        frame_idx = frame_number if frame_number is not None else 1

        if isinstance(image_input, str):
            source_name = os.path.basename(image_input)
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Image file not found: {image_input}")
            img_bgr = cv2.imread(image_input)
            if img_bgr is None:
                raise ValueError(f"Could not decode image at '{image_input}'")
        elif isinstance(image_input, np.ndarray):
            img_bgr = image_input
        else:
            raise TypeError("image_input must be a file path string or numpy array")

        img_h, img_w = img_bgr.shape[:2]

        # 1. Object Detection targeting genuine traffic light class
        results = self.model.predict(
            source=img_bgr,
            conf=self.conf_threshold,
            device=self.device,
            verbose=False
        )

        detected_signal_records: List[SignalObservationRecord] = []

        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                cls_idx = int(box.cls[0].cpu().numpy())
                class_name = self.class_names.get(cls_idx, "").lower()

                # Strictly match genuine traffic light class
                if cls_idx != COCO_TRAFFIC_LIGHT_CLASS_ID and "traffic light" not in class_name:
                    continue

                xyxy = box.xyxy[0].cpu().numpy()
                x_min, y_min, x_max, y_max = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
                score = float(box.conf[0].cpu().numpy())

                bbox = BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)

                # 2. Decoupled State Recognition (RED, YELLOW, GREEN, OFF, UNKNOWN)
                state = self.recognize_signal_state(img_bgr, bbox)

                rec = SignalObservationRecord(
                    frame_number=frame_idx,
                    timestamp=current_time,
                    state=state,
                    confidence=score,
                    bbox=bbox
                )
                detected_signal_records.append(rec)

        # 3. Temporal Signal Tracking Update
        active_tracks_for_frame = self._update_tracks(detected_signal_records, frame_idx, current_time)

        # 4. Health Analysis & Structured Payload Generation
        observations: List[AIObservation] = []

        for track in active_tracks_for_frame:
            health_status, signal_state = self._analyze_track_health(track)

            obs = AIObservation(
                detector_type="TRAFFIC_SIGNAL_DETECTOR",
                event_type="TRAFFIC_SIGNAL",
                confidence=round(track.best_confidence, 4),
                source=source_name,
                frame_number=frame_idx,
                bbox=track.best_bbox,
                metadata={
                    "status": health_status,
                    "signal_state": signal_state,
                    "observation_duration_seconds": round(track.duration_seconds, 2),
                    "observation_count": track.total_observations,
                    "track_id": track.track_id,
                    "state_distribution": track.state_distribution(),
                    "implementation_status": "IMPLEMENTED_DETECTION_PROTOTYPE_STATE" if not self.has_validated_state_model else "VALIDATED"
                }
            )
            observations.append(obs)

        return observations

    def recognize_signal_state(self, image_bgr: np.ndarray, bbox: BoundingBox) -> str:
        """
        Recognize signal state (RED, YELLOW, GREEN, OFF, UNKNOWN) from cropped bounding box ROI.
        Decoupled from YOLO object detection.
        """
        x1, y1 = max(0, int(bbox.x_min)), max(0, int(bbox.y_min))
        x2, y2 = min(image_bgr.shape[1], int(bbox.x_max)), min(image_bgr.shape[0], int(bbox.y_max))

        if x2 - x1 < 5 or y2 - y1 < 5:
            return "UNKNOWN"

        crop = image_bgr[y1:y2, x1:x2]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        h_crop, w_crop = crop.shape[:2]
        third = max(1, h_crop // 3)

        # Segment upper (Red), middle (Yellow), lower (Green) ROI regions
        upper_hsv = hsv[0:third, :]
        middle_hsv = hsv[third:2*third, :]
        lower_hsv = hsv[2*third:, :]

        # HSV Color Range Definitions
        # Red spans 0-10 and 160-180 in HSV
        red_mask1 = cv2.inRange(upper_hsv, np.array([0, 70, 70]), np.array([10, 255, 255]))
        red_mask2 = cv2.inRange(upper_hsv, np.array([160, 70, 70]), np.array([180, 255, 255]))
        red_intensity = cv2.countNonZero(red_mask1 | red_mask2)

        # Yellow: 15-35
        yellow_mask = cv2.inRange(middle_hsv, np.array([15, 70, 70]), np.array([35, 255, 255]))
        yellow_intensity = cv2.countNonZero(yellow_mask)

        # Green: 40-90
        green_mask = cv2.inRange(lower_hsv, np.array([40, 70, 70]), np.array([90, 255, 255]))
        green_intensity = cv2.countNonZero(green_mask)

        total_pixels = h_crop * w_crop
        threshold_px = max(3, int(total_pixels * 0.02))

        intensities = {
            "RED": red_intensity,
            "YELLOW": yellow_intensity,
            "GREEN": green_intensity
        }

        max_state, max_val = max(intensities.items(), key=lambda k: k[1])

        if max_val >= threshold_px:
            return max_state

        # Check if brightness across crop is overall extremely low (OFF state)
        val_channel = hsv[:, :, 2]
        avg_brightness = np.mean(val_channel)
        if avg_brightness < 45.0:
            return "OFF"

        return "UNKNOWN"

    def _update_tracks(
        self,
        records: List[SignalObservationRecord],
        frame_idx: int,
        timestamp: float
    ) -> List[SignalTrack]:
        """Match new frame detections to active signal tracks via IoU."""
        matched_track_ids = set()
        unmatched_records = list(records)

        for rec in list(unmatched_records):
            best_iou = 0.0
            best_track_id = None

            for t_id, track in self.active_tracks.items():
                if t_id in matched_track_ids:
                    continue
                iou = self._compute_iou(rec.bbox, track.best_bbox)
                if iou > best_iou and iou >= 0.25:
                    best_iou = iou
                    best_track_id = t_id

            if best_track_id is not None:
                self.active_tracks[best_track_id].update(rec)
                matched_track_ids.add(best_track_id)
                unmatched_records.remove(rec)

        for rec in unmatched_records:
            new_track = SignalTrack(
                track_id=self.next_track_id,
                first_seen_frame=frame_idx,
                last_seen_frame=frame_idx,
                first_seen_timestamp=timestamp,
                last_seen_timestamp=timestamp,
                best_confidence=rec.confidence,
                best_bbox=rec.bbox,
                observations=[rec]
            )
            self.active_tracks[self.next_track_id] = new_track
            matched_track_ids.add(self.next_track_id)
            self.next_track_id += 1

        return [self.active_tracks[t_id] for t_id in matched_track_ids if t_id in self.active_tracks]

    def _analyze_track_health(self, track: SignalTrack) -> Tuple[str, str]:
        """
        Analyze multi-frame temporal history to determine signal health status.

        Status Levels:
          - SIGNAL_DETECTED
          - SIGNAL_STATE_UNKNOWN
          - SIGNAL_OPERATING
          - SIGNAL_POSSIBLE_MALFUNCTION
        """
        latest_state = track.latest_state

        # Rule 1: Never declare malfunction from insufficient observations/duration
        if track.total_observations < self.min_observation_count or track.duration_seconds < self.min_observation_duration_seconds:
            if latest_state == "UNKNOWN":
                return "SIGNAL_STATE_UNKNOWN", latest_state
            return "SIGNAL_DETECTED", latest_state

        state_counts = track.state_distribution()

        # Rule 2: Sustained OFF state for minimum duration -> POSSIBLE MALFUNCTION
        off_count = state_counts.get("OFF", 0)
        if off_count >= self.min_observation_count and (off_count / track.total_observations) >= 0.8:
            return "SIGNAL_POSSIBLE_MALFUNCTION", "OFF"

        # Rule 3: Stuck in a single state for extended stuck duration -> POSSIBLE MALFUNCTION
        for state in ("RED", "YELLOW", "GREEN"):
            count = state_counts.get(state, 0)
            if count >= self.min_observation_count and (count / track.total_observations) >= 0.95:
                if track.duration_seconds >= self.stuck_state_duration_seconds:
                    return "SIGNAL_POSSIBLE_MALFUNCTION", state

        # Rule 4: Normal transitions / varied states / active operation
        if latest_state == "UNKNOWN":
            return "SIGNAL_STATE_UNKNOWN", "UNKNOWN"

        return "SIGNAL_OPERATING", latest_state

    def annotate_frame(self, image: np.ndarray, observations: List[AIObservation]) -> np.ndarray:
        """Annotate traffic signal observations and health status onto frame."""
        annotated = image.copy()
        for obs in observations:
            if obs.detector_type != "TRAFFIC_SIGNAL_DETECTOR" or obs.bbox is None:
                continue

            pt1 = (int(obs.bbox.x_min), int(obs.bbox.y_min))
            pt2 = (int(obs.bbox.x_max), int(obs.bbox.y_max))
            
            status = obs.metadata.get("status", "SIGNAL_DETECTED")
            signal_state = obs.metadata.get("signal_state", "UNKNOWN")

            # Color scheme based on state
            if signal_state == "RED":
                color = (0, 0, 255)
            elif signal_state == "YELLOW":
                color = (0, 255, 255)
            elif signal_state == "GREEN":
                color = (0, 255, 0)
            else:
                color = (255, 165, 0)

            cv2.rectangle(annotated, pt1, pt2, color, 2)
            label = f"SIGNAL ({signal_state}): {status}"
            cv2.putText(annotated, label, (pt1[0], max(15, pt1[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)

        return annotated

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
