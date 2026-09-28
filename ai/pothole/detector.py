"""
Pothole Detector Module.

Uses an authentic Pothole-trained Ultralytics YOLO model to detect potholes
and road surface anomalies in images and video streams.

MODEL METADATA & VALIDATION SPECIFICATION:
- Default Weights: ai/models/pothole_model.pt (Harisanth/Pothole-Finetuned-YOLOv8)
- Architecture: YOLOv8s fine-tuned on single-class Roboflow pothole dataset (100 epochs)
- Model Class Map (model.names): {0: '0'}
- Verification Status: Single-class detection model where class index 0 represents the single pothole class.
- Security Policy: Generic 80-class COCO models (e.g. yolov8n.pt) are strictly REJECTED on initialization.
"""

from dataclasses import dataclass, field
import logging
import os
import time
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from ultralytics import YOLO

from ai.common.models import AIObservation, BoundingBox
from ai.pothole.downloader import DEFAULT_POTHOLE_MODEL_PATH

logger = logging.getLogger("PotholeDetector")


class PotholeDetector:
    """YOLO-based Pothole Detector using authentic pothole-trained weights."""

    def __init__(
        self,
        model_path: str = DEFAULT_POTHOLE_MODEL_PATH,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        device: str = "cpu",
        require_pothole_class: bool = True
    ):
        """
        Initialize the Pothole Detector.

        Args:
            model_path: Path to pothole-trained YOLO weights (.pt or .onnx).
            conf_threshold: Minimum confidence threshold (0.0 to 1.0).
            iou_threshold: Non-Maximum Suppression (NMS) IoU threshold.
            device: Compute device ('cpu', 'cuda', etc.).
            require_pothole_class: If True, validates that model is NOT a generic COCO model.
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.device = device

        logger.info(f"Loading pothole YOLO model from '{model_path}' on device '{device}'...")
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Pothole model weights file not found at '{model_path}'. "
                "Please run 'python -m ai.pothole.downloader' to obtain verified pothole weights."
            )

        try:
            self.model = YOLO(model_path)
        except Exception as e:
            logger.error(f"Failed to load YOLO model from '{model_path}': {e}")
            raise e

        # Extract authentic class names directly from model definition
        self.class_names = self.model.names if hasattr(self.model, "names") else {}
        logger.info(f"Pothole model loaded successfully. Authentic class names (model.names): {self.class_names}")

        # Validate that the model is NOT a generic 80-class COCO object detector
        if require_pothole_class:
            self._validate_pothole_model(model_path)

    def _validate_pothole_model(self, model_path: str):
        """
        Validate that the loaded YOLO model is an authentic pothole detector.
        Rejects generic 80-class COCO models (yolov8n.pt with 80 classes) and unvalidated multi-class models.
        """
        # 1. Explicitly reject generic 80-class COCO object detectors
        if len(self.class_names) == 80 and self.class_names.get(0) == "person":
            raise ValueError(
                f"Model at '{model_path}' is a generic COCO dataset model (80 classes: person, car, dog...). "
                "Arbitrary class remapping of generic COCO models to potholes is strictly prohibited. "
                "Please provide an authentic pothole-trained YOLO model."
            )

        # 2. Check if model explicitly contains 'pothole' class or is a verified single-class model
        has_pothole_label = any("pothole" in str(name).lower() for name in self.class_names.values())
        is_single_class = (len(self.class_names) == 1)

        if not (has_pothole_label or is_single_class):
            raise ValueError(
                f"Model at '{model_path}' with class names {self.class_names} could not be validated "
                "as a pothole model. Expected a model with class name containing 'pothole' or a single-class defect model."
            )

    def set_confidence_threshold(self, conf_threshold: float):
        """Update confidence threshold dynamically."""
        if not (0.0 <= conf_threshold <= 1.0):
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        self.conf_threshold = conf_threshold
        logger.info(f"Pothole confidence threshold updated to {self.conf_threshold}")

    def detect_frame(
        self,
        image_input: Union[str, np.ndarray],
        conf_threshold: Optional[float] = None,
        source_name: str = "frame",
        frame_number: Optional[int] = None
    ) -> List[AIObservation]:
        """
        Run pothole detection on a single frame and return a list of standardized AIObservations.
        """
        conf = conf_threshold if conf_threshold is not None else self.conf_threshold

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
        total_img_area = img_h * img_w

        results = self.model.predict(
            source=img_bgr,
            conf=conf,
            iou=self.iou_threshold,
            device=self.device,
            verbose=False
        )

        observations: List[AIObservation] = []

        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                x_min, y_min, x_max, y_max = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
                score = float(box.conf[0].cpu().numpy())
                cls_idx = int(box.cls[0].cpu().numpy())

                raw_name = self.class_names.get(cls_idx, f"class_{cls_idx}")
                cls_name = "POTHOLE" if str(raw_name).lower() in ("0", "pothole") else str(raw_name).upper()

                bbox = BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)
                area_ratio = bbox.area_px / total_img_area if total_img_area > 0 else 0.0

                obs = AIObservation(
                    detector_type="POTHOLE_DETECTOR",
                    event_type=cls_name,
                    confidence=score,
                    source=source_name,
                    frame_number=frame_number,
                    bbox=bbox,
                    metadata={
                        "class_id": cls_idx,
                        "class_name": cls_name,
                        "estimated_area_px": round(bbox.area_px, 2),
                        "estimated_area_ratio": round(area_ratio, 6),
                    }
                )
                observations.append(obs)

        return observations

    def annotate_frame(self, image: np.ndarray, observations: List[AIObservation]) -> np.ndarray:
        """Draw styled bounding boxes and labels for pothole observations on an image."""
        annotated = image.copy()
        for obs in observations:
            if obs.detector_type != "POTHOLE_DETECTOR" or obs.bbox is None:
                continue

            pt1 = (int(obs.bbox.x_min), int(obs.bbox.y_min))
            pt2 = (int(obs.bbox.x_max), int(obs.bbox.y_max))
            color = (0, 0, 255)  # Bright Red

            cv2.rectangle(annotated, pt1, pt2, color, 2)
            label = f"{obs.event_type}: {obs.confidence:.2f}"
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)

            label_bg_pt1 = (pt1[0], max(0, pt1[1] - h - 6))
            label_bg_pt2 = (pt1[0] + w + 6, max(h + 6, pt1[1]))
            cv2.rectangle(annotated, label_bg_pt1, label_bg_pt2, color, -1)

            text_pt = (pt1[0] + 3, max(h + 2, pt1[1] - 3))
            cv2.putText(annotated, label, text_pt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        return annotated
