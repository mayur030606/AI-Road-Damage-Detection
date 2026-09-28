"""
Zebra Crossing & Pedestrian Marking Detector Interface [PROTOTYPE / REQUIRES TRAINED MODEL].

Analyzes road frames for pedestrian zebra crossing presence and degradation status.
Currently implemented as a structural prototype awaiting fine-tuned segmentation weights.
Does NOT generate fabricated detection results.
"""

import logging
import os
from typing import List, Optional, Union
import cv2
import numpy as np

from ai.common.models import AIObservation, BoundingBox

logger = logging.getLogger("ZebraCrossingDetector")


class ZebraCrossingDetector:
    """
    Zebra Crossing Detection Interface.
    Status: PROTOTYPE / REQUIRES TRAINED SEGMENTATION MODEL.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.3,
        device: str = "cpu"
    ):
        """
        Initialize Zebra Crossing Detector.

        Args:
            model_path: Optional path to dedicated Zebra Crossing weights.
            conf_threshold: Minimum confidence threshold.
            device: Compute device.
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.device = device
        self.is_model_available = model_path is not None and os.path.exists(model_path)

        if not self.is_model_available:
            logger.warning(
                "No dedicated Zebra Crossing segmentation model weights provided. "
                "Module operating in PROTOTYPE mode. Will return UNKNOWN status until model is loaded."
            )

    def detect_frame(
        self,
        image_input: Union[str, np.ndarray],
        source_name: str = "frame",
        frame_number: Optional[int] = None
    ) -> List[AIObservation]:
        """
        Analyze frame for Zebra Crossing presence and degradation.

        Returns:
            List containing a standardized AIObservation with status 'UNKNOWN', 'DETECTED', or 'MISSING'.
        """
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

        # If dedicated model is available in future, run inference here
        if self.is_model_available:
            # Model inference placeholder for trained weights
            status = "UNKNOWN"
            confidence = 0.0
            bbox = None
        else:
            # Prototype stub: Transparently reports UNKNOWN state (no fake detections)
            status = "UNKNOWN"
            confidence = 0.0
            bbox = None

        obs = AIObservation(
            detector_type="ZEBRA_CROSSING_DETECTOR",
            event_type=f"ZEBRA_CROSSING_{status}",
            confidence=confidence,
            source=source_name,
            frame_number=frame_number,
            bbox=bbox,
            metadata={
                "status": status,
                "implementation_status": "PROTOTYPE",
                "requires_model": "Zebra-Crossing-YOLOv8-Segmentation",
                "message": "Zebra crossing module requires a fine-tuned segmentation model. Operating in structural prototype mode."
            }
        )
        return [obs]

    def annotate_frame(self, image: np.ndarray, observations: List[AIObservation]) -> np.ndarray:
        """Annotate zebra crossing observation status onto frame."""
        annotated = image.copy()
        for obs in observations:
            if obs.detector_type != "ZEBRA_CROSSING_DETECTOR":
                continue
            status = obs.metadata.get("status", "UNKNOWN")
            label = f"ZEBRA CROSSING: {status} (PROTOTYPE)"
            cv2.putText(annotated, label, (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2, cv2.LINE_AA)
        return annotated
