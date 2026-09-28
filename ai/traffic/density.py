"""
Traffic Density Estimator Module.

Estimates road traffic density by detecting and counting relevant vehicles
(car, bus, truck, motorcycle) in the camera frame or a designated Region of Interest (ROI).
Uses authentic vehicle model class names directly from Ultralytics YOLO.
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

logger = logging.getLogger("TrafficDensityEstimator")

# COCO standard vehicle classes
DEFAULT_VEHICLE_CLASSES = ["car", "bus", "truck", "motorcycle", "bicycle"]


class TrafficDensityEstimator:
    """Estimates traffic density (LOW, MEDIUM, HIGH) via vehicle detection and counting."""

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.25,
        device: str = "cpu",
        low_threshold: int = 2,
        medium_threshold: int = 6,
        target_vehicle_classes: Optional[List[str]] = None
    ):
        """
        Initialize Traffic Density Estimator.

        Args:
            model_path: YOLO model weights containing vehicle classes (e.g., yolov8n.pt).
            conf_threshold: Confidence threshold for vehicle detection.
            device: Compute device ('cpu', 'cuda').
            low_threshold: Max vehicle count for LOW density (0 to low_threshold).
            medium_threshold: Max vehicle count for MEDIUM density (low+1 to medium_threshold).
            target_vehicle_classes: List of vehicle class names to count.
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.device = device
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.target_vehicle_classes = [c.lower() for c in (target_vehicle_classes or DEFAULT_VEHICLE_CLASSES)]

        logger.info(f"Loading vehicle detection model from '{model_path}' on device '{device}'...")
        try:
            self.model = YOLO(model_path)
        except Exception as e:
            logger.error(f"Failed to load vehicle model from '{model_path}': {e}")
            raise e

        # Extract authentic class names directly from model.names
        self.class_names = self.model.names if hasattr(self.model, "names") else {}
        logger.info(f"Vehicle model loaded successfully. Authentic model classes (model.names): {self.class_names}")

        # Map target vehicle class names to model class indices
        self.vehicle_class_indices = [
            idx for idx, name in self.class_names.items()
            if str(name).lower() in self.target_vehicle_classes
        ]
        logger.info(f"Matched vehicle class indices: {self.vehicle_class_indices} ({[self.class_names[i] for i in self.vehicle_class_indices]})")

    def estimate_density(
        self,
        image_input: Union[str, np.ndarray],
        roi_bbox: Optional[BoundingBox] = None,
        source_name: str = "frame",
        frame_number: Optional[int] = None
    ) -> List[AIObservation]:
        """
        Detect vehicles and calculate traffic density level (LOW, MEDIUM, HIGH).

        Args:
            image_input: File path string or OpenCV BGR image array.
            roi_bbox: Optional Region of Interest bounding box to restrict counting.
            source_name: Source frame name.
            frame_number: Frame index.

        Returns:
            List containing a single standardized AIObservation for traffic density.
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

        img_h, img_w = img_bgr.shape[:2]

        results = self.model.predict(
            source=img_bgr,
            conf=self.conf_threshold,
            classes=self.vehicle_class_indices if self.vehicle_class_indices else None,
            device=self.device,
            verbose=False
        )

        detected_vehicles = []
        vehicle_counts_by_class: Dict[str, int] = {}

        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                x_min, y_min, x_max, y_max = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
                score = float(box.conf[0].cpu().numpy())
                cls_idx = int(box.cls[0].cpu().numpy())
                cls_name = str(self.class_names.get(cls_idx, f"vehicle_{cls_idx}")).lower()

                # Check if centroid falls within ROI (if ROI specified)
                center_x = (x_min + x_max) / 2.0
                center_y = (y_min + y_max) / 2.0

                if roi_bbox is not None:
                    if not (roi_bbox.x_min <= center_x <= roi_bbox.x_max and roi_bbox.y_min <= center_y <= roi_bbox.y_max):
                        continue

                detected_vehicles.append({
                    "class_name": cls_name,
                    "confidence": round(score, 4),
                    "bbox": [round(x_min, 2), round(y_min, 2), round(x_max, 2), round(y_max, 2)]
                })

                vehicle_counts_by_class[cls_name] = vehicle_counts_by_class.get(cls_name, 0) + 1

        total_vehicles = len(detected_vehicles)

        # Classify density into LOW, MEDIUM, HIGH
        if total_vehicles <= self.low_threshold:
            density_level = "LOW"
        elif total_vehicles <= self.medium_threshold:
            density_level = "MEDIUM"
        else:
            density_level = "HIGH"

        # Calculate confidence metric based on average vehicle detection confidence
        avg_conf = (
            sum(v["confidence"] for v in detected_vehicles) / total_vehicles
            if total_vehicles > 0 else 1.0
        )

        obs = AIObservation(
            detector_type="TRAFFIC_DENSITY_ESTIMATOR",
            event_type=f"TRAFFIC_DENSITY_{density_level}",
            confidence=round(avg_conf, 4),
            source=source_name,
            frame_number=frame_number,
            bbox=roi_bbox,
            metadata={
                "density_level": density_level,
                "total_vehicles_detected": total_vehicles,
                "vehicle_counts_by_class": vehicle_counts_by_class,
                "thresholds": {"low_max": self.low_threshold, "medium_max": self.medium_threshold},
                "vehicles": detected_vehicles,
                "methodology": "MVP ROI vehicle detection & volumetric counting"
            }
        )

        logger.info(f"Traffic density on '{source_name}': {density_level} ({total_vehicles} vehicle(s) detected)")
        return [obs]

    def annotate_frame(self, image: np.ndarray, observations: List[AIObservation]) -> np.ndarray:
        """Annotate vehicle detections and traffic density overlay onto image."""
        annotated = image.copy()
        for obs in observations:
            if obs.detector_type != "TRAFFIC_DENSITY_ESTIMATOR":
                continue

            density_level = obs.metadata.get("density_level", "UNKNOWN")
            total_vehicles = obs.metadata.get("total_vehicles_detected", 0)

            # Draw vehicle bounding boxes
            for v in obs.metadata.get("vehicles", []):
                bbox = v["bbox"]
                pt1 = (int(bbox[0]), int(bbox[1]))
                pt2 = (int(bbox[2]), int(bbox[3]))
                cv2.rectangle(annotated, pt1, pt2, (255, 191, 0), 2)  # Deep cyan/amber

            # Draw density HUD banner at top
            color_map = {"LOW": (0, 200, 0), "MEDIUM": (0, 165, 255), "HIGH": (0, 0, 255)}
            banner_color = color_map.get(density_level, (128, 128, 128))

            label = f"TRAFFIC DENSITY: {density_level} ({total_vehicles} Vehicles)"
            cv2.rectangle(annotated, (10, 10), (450, 45), (0, 0, 0), -1)
            cv2.putText(annotated, label, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, banner_color, 2, cv2.LINE_AA)

        return annotated
