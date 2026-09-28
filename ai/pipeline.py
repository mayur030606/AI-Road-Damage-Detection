"""
Unified AI Perception Pipeline for SIH26124.

Orchestrates Pothole Detector, Zebra Crossing Detector, and Traffic Density Estimator
over road images/video frames to produce consolidated PipelineResult outputs.
"""

import logging
import os
import time
from typing import Dict, List, Optional, Union

import cv2
import numpy as np

from ai.common.models import AIObservation, PipelineResult
from ai.pothole.detector import PotholeDetector
from ai.zebra_crossing.detector import ZebraCrossingDetector
from ai.traffic.density import TrafficDensityEstimator
from ai.traffic_signal.detector import TrafficSignalDetector
from ai.pothole.downloader import DEFAULT_POTHOLE_MODEL_PATH

logger = logging.getLogger("AIPipeline")


class AIPipeline:
    """Unified AI perception pipeline aggregating all 3 core sensing modules."""

    def __init__(
        self,
        pothole_model_path: str = DEFAULT_POTHOLE_MODEL_PATH,
        vehicle_model_path: str = "yolov8n.pt",
        pothole_conf: float = 0.25,
        traffic_conf: float = 0.25,
        device: str = "cpu",
        run_pothole: bool = True,
        run_zebra: bool = True,
        run_traffic: bool = True,
        run_traffic_signal: bool = True,
        signal_model_path: str = "yolov8n.pt",
        signal_conf: float = 0.25
    ):
        """
        Initialize the unified perception pipeline.

        Args:
            pothole_model_path: Path to authentic pothole weights file.
            vehicle_model_path: Path to vehicle detection weights file.
            pothole_conf: Pothole confidence threshold.
            traffic_conf: Vehicle detection confidence threshold.
            device: Compute device ('cpu', 'cuda').
            run_pothole: Whether to execute Pothole Detector module.
            run_zebra: Whether to execute Zebra Crossing Detector prototype.
            run_traffic: Whether to execute Traffic Density Estimator module.
        """
        self.run_pothole = run_pothole
        self.run_zebra = run_zebra
        self.run_traffic = run_traffic
        self.run_traffic_signal = run_traffic_signal

        logger.info("Initializing Unified SIH26124 AI Perception Pipeline...")

        self.pothole_detector = None
        if run_pothole:
            if not os.path.exists(pothole_model_path):
                logger.info(f"Pothole weights not found at '{pothole_model_path}'. Running automatic downloader...")
                from ai.pothole.downloader import download_pothole_model
                download_pothole_model(pothole_model_path)
            self.pothole_detector = PotholeDetector(
                model_path=pothole_model_path,
                conf_threshold=pothole_conf,
                device=device
            )

        self.zebra_detector = None
        if run_zebra:
            self.zebra_detector = ZebraCrossingDetector(conf_threshold=0.3, device=device)

        self.traffic_estimator = None
        if run_traffic:
            self.traffic_estimator = TrafficDensityEstimator(
                model_path=vehicle_model_path,
                conf_threshold=traffic_conf,
                device=device
            )

        self.signal_detector = None
        if run_traffic_signal:
            self.signal_detector = TrafficSignalDetector(
                model_path=signal_model_path,
                conf_threshold=signal_conf,
                device=device
            )

        logger.info("Unified AI Pipeline initialized successfully.")

    def process_frame(
        self,
        image_input: Union[str, np.ndarray],
        source_name: str = "frame",
        frame_number: Optional[int] = None,
        draw_annotations: bool = True
    ) -> PipelineResult:
        """
        Execute all active AI modules on a single frame and return a unified PipelineResult.
        """
        t0 = time.perf_counter()

        if isinstance(image_input, str):
            source_name = os.path.basename(image_input)
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Image file not found: {image_input}")
            img_bgr = cv2.imread(image_input)
            if img_bgr is None:
                raise ValueError(f"Could not decode image at '{image_input}'")
        elif isinstance(image_input, np.ndarray):
            img_bgr = image_input.copy()
        else:
            raise TypeError("image_input must be a file path string or numpy array")

        img_h, img_w = img_bgr.shape[:2]
        all_observations: List[AIObservation] = []

        # 1. Execute Pothole Detection
        if self.pothole_detector is not None:
            pothole_obs = self.pothole_detector.detect_frame(
                image_input=img_bgr,
                source_name=source_name,
                frame_number=frame_number
            )
            all_observations.extend(pothole_obs)

        # 2. Execute Zebra Crossing Detection
        if self.zebra_detector is not None:
            zebra_obs = self.zebra_detector.detect_frame(
                image_input=img_bgr,
                source_name=source_name,
                frame_number=frame_number
            )
            all_observations.extend(zebra_obs)

        # 3. Execute Traffic Density Estimation
        if self.traffic_estimator is not None:
            traffic_obs = self.traffic_estimator.estimate_density(
                image_input=img_bgr,
                source_name=source_name,
                frame_number=frame_number
            )
            all_observations.extend(traffic_obs)

        # 4. Execute Traffic Signal Intelligence
        if self.signal_detector is not None:
            signal_obs = self.signal_detector.detect_frame(
                image_input=img_bgr,
                source_name=source_name,
                frame_number=frame_number
            )
            all_observations.extend(signal_obs)

        inference_time_ms = (time.perf_counter() - t0) * 1000.0

        # Render combined annotations
        annotated_img = img_bgr.copy() if draw_annotations else None
        if draw_annotations and annotated_img is not None:
            if self.traffic_estimator is not None:
                annotated_img = self.traffic_estimator.annotate_frame(annotated_img, all_observations)
            if self.pothole_detector is not None:
                annotated_img = self.pothole_detector.annotate_frame(annotated_img, all_observations)
            if self.zebra_detector is not None:
                annotated_img = self.zebra_detector.annotate_frame(annotated_img, all_observations)
            if self.signal_detector is not None:
                annotated_img = self.signal_detector.annotate_frame(annotated_img, all_observations)

        result = PipelineResult(
            source=source_name,
            image_width=img_w,
            image_height=img_h,
            observations=all_observations,
            inference_time_ms=inference_time_ms,
            annotated_image=annotated_img
        )

        logger.info(f"Pipeline processed '{source_name}': {result.total_observations} total observation(s) in {inference_time_ms:.1f}ms")
        return result
