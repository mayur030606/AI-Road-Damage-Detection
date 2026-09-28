"""
Unified Real-Time Road Intelligence Video Processing Pipeline.

Processes road video streams frame-by-frame, executing Pothole Detection,
Zebra Crossing Analysis, and Traffic Density Estimation with temporal tracking,
performance profiling, annotated video output, and structured JSON reporting.
"""

from dataclasses import dataclass, field
import datetime
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union

import cv2
import numpy as np

from ai.common.models import AIObservation, BoundingBox, PipelineResult, SingleDetection
from ai.pipeline import AIPipeline
from ai.pothole.downloader import DEFAULT_POTHOLE_MODEL_PATH
from ai.tracker import DefectTracker
from ai.aggregator import EventAggregator

logger = logging.getLogger("RoadIntelligencePipeline")


@dataclass
class PerformanceMetrics:
    """Profiling metrics for video pipeline execution."""
    total_frames_in_source: int
    processed_frames: int
    elapsed_seconds: float
    average_fps: float
    avg_inference_time_ms: float
    min_inference_time_ms: float
    max_inference_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_frames_in_source": self.total_frames_in_source,
            "processed_frames": self.processed_frames,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "average_fps": round(self.average_fps, 2),
            "avg_inference_time_ms": round(self.avg_inference_time_ms, 2),
            "min_inference_time_ms": round(self.min_inference_time_ms, 2),
            "max_inference_time_ms": round(self.max_inference_time_ms, 2),
        }


@dataclass
class VideoPipelineSummary:
    """Consolidated summary output for video stream processing."""
    source_video: str
    output_video_path: Optional[str]
    output_json_path: Optional[str]
    performance: PerformanceMetrics
    model_info: Dict[str, Any]
    unique_pothole_events_count: int
    unique_pothole_events: List[Dict[str, Any]]
    traffic_density_distribution: Dict[str, int]
    zebra_crossing_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_video": self.source_video,
            "output_video_path": self.output_video_path,
            "output_json_path": self.output_json_path,
            "performance_metrics": self.performance.to_dict(),
            "model_info": self.model_info,
            "pothole_summary": {
                "unique_aggregated_events_count": self.unique_pothole_events_count,
                "aggregated_events": self.unique_pothole_events
            },
            "traffic_summary": {
                "density_distribution": self.traffic_density_distribution
            },
            "zebra_summary": {
                "status": self.zebra_crossing_status,
                "implementation": "PROTOTYPE / REQUIRES TRAINED MODEL"
            }
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class UnifiedRoadIntelligencePipeline:
    """
    Frame-by-frame video processing engine combining Pothole Detection,
    Traffic Density Estimation, Zebra Crossing Prototype, and Temporal Aggregation.
    """

    def __init__(
        self,
        pothole_model_path: str = DEFAULT_POTHOLE_MODEL_PATH,
        vehicle_model_path: str = "yolov8n.pt",
        pothole_conf: float = 0.25,
        traffic_conf: float = 0.25,
        low_traffic_threshold: int = 2,
        medium_traffic_threshold: int = 6,
        device: str = "cpu",
        device_id: str = "BUS-EDGE-001"
    ):
        """
        Initialize Road Intelligence Pipeline.

        Args:
            pothole_model_path: Path to authentic pothole YOLO model.
            vehicle_model_path: Path to vehicle detection YOLO model.
            pothole_conf: Confidence threshold for potholes.
            traffic_conf: Confidence threshold for vehicle detection.
            low_traffic_threshold: Vehicle count upper limit for LOW traffic density.
            medium_traffic_threshold: Vehicle count upper limit for MEDIUM traffic density.
            device: Compute device ('cpu', 'cuda').
            device_id: Bus sensing unit identifier.
        """
        self.device_id = device_id
        self.pothole_model_path = pothole_model_path
        self.vehicle_model_path = vehicle_model_path

        logger.info("Initializing Unified Road Intelligence Pipeline...")

        self.perception_pipeline = AIPipeline(
            pothole_model_path=pothole_model_path,
            vehicle_model_path=vehicle_model_path,
            pothole_conf=pothole_conf,
            traffic_conf=traffic_conf,
            device=device,
            run_pothole=True,
            run_zebra=True,
            run_traffic=True
        )

        # Configure traffic density thresholds
        if self.perception_pipeline.traffic_estimator is not None:
            self.perception_pipeline.traffic_estimator.low_threshold = low_traffic_threshold
            self.perception_pipeline.traffic_estimator.medium_threshold = medium_traffic_threshold

        self.event_aggregator = EventAggregator(device_id=device_id)
        logger.info("Road Intelligence Pipeline initialized successfully.")

    def process_video(
        self,
        video_path: Union[str, int],
        output_video_path: Optional[str] = None,
        output_json_path: Optional[str] = None,
        max_frames: Optional[int] = None,
        conf_override: Optional[float] = None
    ) -> VideoPipelineSummary:
        """
        Process input video stream frame-by-frame and output annotated video and JSON results.

        Args:
            video_path: Path to video file OR camera index integer/string.
            output_video_path: Optional path to save annotated .mp4 output.
            output_json_path: Optional path to save structured .json results.
            max_frames: Optional frame limit.
            conf_override: Optional confidence override for potholes.

        Returns:
            VideoPipelineSummary object with performance metrics and aggregated events.
        """
        is_camera = False
        if isinstance(video_path, int):
            is_camera = True
            cap_source = video_path
        elif isinstance(video_path, str) and video_path.isdigit():
            is_camera = True
            cap_source = int(video_path)
        else:
            cap_source = str(video_path)
            if not os.path.exists(cap_source):
                raise FileNotFoundError(f"Video file not found at '{cap_source}'")

        cap = cv2.VideoCapture(cap_source)
        if not cap.isOpened():
            raise ValueError(f"Could not open video source at '{video_path}'")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames_in_source = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if not is_camera else -1

        logger.info(f"Opened video source '{video_path}' ({width}x{height} @ {fps:.1f} FPS, total frames: {total_frames_in_source})")

        # Initialize VideoWriter if output path provided
        writer = None
        if output_video_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))

        # Temporal object tracker for pothole deduplication
        tracker = DefectTracker(iou_match_threshold=0.25, max_lost_frames=5)
        emitted_pothole_events = []
        traffic_density_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        inference_times: List[float] = []

        frame_idx = 0
        start_wall_time = time.perf_counter()
        source_base_name = "camera_stream" if is_camera else os.path.basename(str(video_path))

        while cap.isOpened():
            if max_frames and frame_idx >= max_frames:
                logger.info(f"Reached user-specified maximum frame limit of {max_frames} frames.")
                break

            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1

            # Process single frame through unified perception pipeline
            frame_res = self.perception_pipeline.process_frame(
                image_input=frame,
                source_name=source_base_name,
                frame_number=frame_idx,
                draw_annotations=(writer is not None)
            )

            inference_times.append(frame_res.inference_time_ms)

            # Extract pothole detections for temporal tracking
            pothole_obs_list = frame_res.get_observations_by_detector("POTHOLE_DETECTOR")
            single_detections = []
            for obs in pothole_obs_list:
                if obs.bbox is not None:
                    single_det = SingleDetection(
                        class_id=obs.metadata.get("class_id", 0),
                        class_name=obs.event_type.lower(),
                        confidence=obs.confidence,
                        bbox=obs.bbox,
                        area_ratio=obs.metadata.get("estimated_area_ratio", 0.0)
                    )
                    single_detections.append(single_det)

            # Update tracker and collect completed defect tracks
            newly_closed = tracker.update(single_detections, frame_idx)
            for track in newly_closed:
                evt = self.event_aggregator.create_event_from_track(track)
                emitted_pothole_events.append(evt.to_dict())

            # Track traffic density metrics
            traffic_obs_list = frame_res.get_observations_by_detector("TRAFFIC_DENSITY_ESTIMATOR")
            for obs in traffic_obs_list:
                d_level = obs.metadata.get("density_level", "LOW")
                traffic_density_counts[d_level] = traffic_density_counts.get(d_level, 0) + 1

            if writer is not None and frame_res.annotated_image is not None:
                writer.write(frame_res.annotated_image)

            if frame_idx % 10 == 0 or frame_idx == max_frames:
                logger.info(f"Processed frame {frame_idx}/{total_frames_in_source} ({frame_res.inference_time_ms:.1f}ms/frame)")

        cap.release()
        if writer is not None:
            writer.release()

        # Flush any remaining active pothole tracks at video end
        final_closed = tracker.flush_remaining_tracks()
        for track in final_closed:
            evt = self.event_aggregator.create_event_from_track(track)
            emitted_pothole_events.append(evt.to_dict())

        elapsed_sec = time.perf_counter() - start_wall_time
        processed_fps = frame_idx / elapsed_sec if elapsed_sec > 0 else 0.0
        avg_inf_ms = sum(inference_times) / len(inference_times) if inference_times else 0.0
        min_inf_ms = min(inference_times) if inference_times else 0.0
        max_inf_ms = max(inference_times) if inference_times else 0.0

        performance = PerformanceMetrics(
            total_frames_in_source=total_frames_in_source,
            processed_frames=frame_idx,
            elapsed_seconds=elapsed_sec,
            average_fps=processed_fps,
            avg_inference_time_ms=avg_inf_ms,
            min_inference_time_ms=min_inf_ms,
            max_inference_time_ms=max_inf_ms
        )

        model_info = {
            "pothole_model": {
                "path": self.pothole_model_path,
                "class_names": self.perception_pipeline.pothole_detector.class_names if self.perception_pipeline.pothole_detector else {}
            },
            "traffic_model": {
                "path": self.vehicle_model_path,
                "class_names": self.perception_pipeline.traffic_estimator.class_names if self.perception_pipeline.traffic_estimator else {}
            }
        }

        summary = VideoPipelineSummary(
            source_video=str(video_path),
            output_video_path=output_video_path,
            output_json_path=output_json_path,
            performance=performance,
            model_info=model_info,
            unique_pothole_events_count=len(emitted_pothole_events),
            unique_pothole_events=emitted_pothole_events,
            traffic_density_distribution=traffic_density_counts,
            zebra_crossing_status="PROTOTYPE / UNKNOWN"
        )

        # Write output JSON if path requested
        if output_json_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
            with open(output_json_path, "w") as f:
                f.write(summary.to_json(indent=2))
            logger.info(f"Saved pipeline execution summary JSON to '{output_json_path}'")

        logger.info(f"Video processing complete: {frame_idx} frames in {elapsed_sec:.2f}s ({processed_fps:.1f} FPS). Unique Potholes: {len(emitted_pothole_events)}")
        return summary
