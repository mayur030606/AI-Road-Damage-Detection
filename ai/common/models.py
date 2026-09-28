"""
Common Data Models for SIH26124 AI Perception Layer.

Defines standardized observation structures emitted by Pothole Detection,
Zebra Crossing Analysis, and Traffic Density Estimation modules.
"""

from dataclasses import dataclass, field
import datetime
import json
from typing import Any, Dict, List, Optional
import numpy as np


@dataclass
class BoundingBox:
    """Standardized bounding box coordinates and metrics."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return max(0.0, self.x_max - self.x_min)

    @property
    def height(self) -> float:
        return max(0.0, self.y_max - self.y_min)

    @property
    def area_px(self) -> float:
        return self.width * self.height

    def to_list(self) -> List[float]:
        return [round(self.x_min, 2), round(self.y_min, 2), round(self.x_max, 2), round(self.y_max, 2)]

    def to_dict(self) -> Dict[str, float]:
        return {
            "x_min": round(self.x_min, 2),
            "y_min": round(self.y_min, 2),
            "x_max": round(self.x_max, 2),
            "y_max": round(self.y_max, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "area_px": round(self.area_px, 2),
        }


@dataclass
class AIObservation:
    """
    Standardized observation output produced by any AI perception module.
    Does not contain GPS or backend-specific fields.
    """
    detector_type: str        # "POTHOLE_DETECTOR", "ZEBRA_CROSSING_DETECTOR", "TRAFFIC_DENSITY_ESTIMATOR"
    event_type: str           # "POTHOLE", "ROAD_CRACK", "ZEBRA_CROSSING_PRESENT", "ZEBRA_CROSSING_MISSING", "TRAFFIC_DENSITY"
    confidence: float         # Confidence score (0.0 to 1.0)
    source: str               # Input image/video name or camera identifier
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    frame_number: Optional[int] = None
    bbox: Optional[BoundingBox] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "detector_type": self.detector_type,
            "event_type": self.event_type,
            "confidence": round(float(self.confidence), 4),
            "source": self.source,
            "timestamp": self.timestamp,
            "frame_number": self.frame_number,
            "bbox": self.bbox.to_list() if self.bbox is not None else None,
            "metadata": self.metadata,
        }
        return result

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class PipelineResult:
    """
    Unified result object aggregating observations from all active AI modules
    for a single frame/image input.
    """
    source: str
    image_width: int
    image_height: int
    observations: List[AIObservation] = field(default_factory=list)
    inference_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    annotated_image: Optional[np.ndarray] = None
    saved_output_path: Optional[str] = None

    @property
    def total_observations(self) -> int:
        return len(self.observations)

    def get_observations_by_detector(self, detector_type: str) -> List[AIObservation]:
        return [obs for obs in self.observations if obs.detector_type == detector_type]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "image_dimensions": {"width": self.image_width, "height": self.image_height},
            "total_observations": self.total_observations,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "saved_output_path": self.saved_output_path,
            "observations": [obs.to_dict() for obs in self.observations],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class SingleDetection:
    """Individual defect detection record used for spatial tracking and aggregation."""
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    area_ratio: float  # Bbox area / Image total area

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_list(),
            "estimated_area_px": round(self.bbox.area_px, 2),
            "estimated_area_ratio": round(self.area_ratio, 6),
        }


@dataclass
class ObservationEvent:
    """Standardized event telemetry payload emitted by edge devices."""
    event_uuid: str
    device_id: str
    defect_type: str
    confidence: float
    estimated_size_sqm: float
    bbox: List[float]
    track_id: Optional[int]
    total_frames_observed: int
    first_seen_timestamp: str
    last_seen_timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_uuid": self.event_uuid,
            "device_id": self.device_id,
            "defect_type": self.defect_type,
            "confidence": round(self.confidence, 4),
            "estimated_size_sqm": round(self.estimated_size_sqm, 4),
            "bbox": self.bbox,
            "track_id": self.track_id,
            "total_frames_observed": self.total_frames_observed,
            "first_seen_timestamp": self.first_seen_timestamp,
            "last_seen_timestamp": self.last_seen_timestamp,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

