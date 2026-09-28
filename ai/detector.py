"""
Edge Computer Vision & Incident Capture Pipeline for SIH26124 Edge Sensing Unit.

Features:
- Raspberry Pi 4/5 64-bit OS (Bookworm) optimized for official CSI Camera Module.
- Hardware-level Auto-Exposure Control (AEC) and Auto-White Balance (AWB).
- Configured for 1280x720 High-Definition capture at 30 Frames Per Second (FPS).
- PyTorch & Ultralytics YOLO inference with fine-tuned pothole weights (ai/models/pothole_model.pt).
- Strict confidence threshold of 0.75 for verified pothole anomalies.
- Thread-safe circular frame buffer (collections.deque) maintaining a 5-second pre-event history
  (150 frames) and recording 5 post-event seconds (150 frames) upon defect detection.
- Asynchronous video writer worker encoding 10-second HD .mp4 clips into ai/video_captures/.
- Integrated dual-head Traffic Density Estimator (yolov8n.pt) computing vehicle count & congestion level.
- Automated incident packaging & REST dispatch to central aggregator.
"""

from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import datetime
import json
import logging
import os
import queue
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import uuid

import cv2
import numpy as np

# Backends (first available wins at load time):
# 1) ultralytics / PyTorch  2) onnxruntime  3) OpenCV DNN (works on Pi Python 3.13)
_ULTRALYTICS_AVAILABLE = False
_ONNX_AVAILABLE = False
_ort = None
YOLO = None

try:
    from ultralytics import YOLO  # type: ignore
    _ULTRALYTICS_AVAILABLE = True
except ImportError:
    pass

try:
    import onnxruntime as _ort  # type: ignore
    _ONNX_AVAILABLE = True
except ImportError:
    _ort = None
    _ONNX_AVAILABLE = False

# Import local aggregator and models
from ai.aggregator import CentralAggregator, GPSProvider

# Configure logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "edge_detector.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("EdgeDetector")

DEFAULT_POTHOLE_MODEL = os.path.join(os.path.dirname(__file__), "models", "pothole_model.pt")
DEFAULT_MODEL_PATH = DEFAULT_POTHOLE_MODEL
DEFAULT_VEHICLE_MODEL = os.path.join(os.path.dirname(__file__), "..", "yolov8n.pt")
DEFAULT_CAPTURES_DIR = os.path.join(os.path.dirname(__file__), "video_captures")


def validate_system_directories():
    """Ensure all required system directories exist before pipeline startup."""
    dirs_to_check = [
        os.path.join(os.path.dirname(__file__), "video_captures"),
        os.path.join(os.path.dirname(__file__), "models"),
        os.path.join(os.path.dirname(__file__), "logs"),
        os.path.join(os.path.dirname(__file__), "queue"),
        os.path.join(os.path.dirname(__file__), "samples"),
    ]
    for d in dirs_to_check:
        os.makedirs(d, exist_ok=True)
    logger.info("System directories validated successfully.")


@dataclass
class BoundingBox:
    """Bounding box coordinates and geometric properties."""
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


@dataclass
class PotholeDetection:
    """Structured record for a detected pothole anomaly."""
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    area_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_list(),
            "area_px": round(self.bbox.area_px, 2),
            "area_ratio": round(self.area_ratio, 6)
        }

# Backward compatibility alias
SingleDetection = PotholeDetection


@dataclass
class FrameDetectionResult:
    """Structured detection result for an image or video frame."""
    source: str
    image_height: int
    image_width: int
    detection_count: int
    detections: List[PotholeDetection] = field(default_factory=list)
    inference_time_ms: float = 0.0
    annotated_image: Optional[np.ndarray] = None
    saved_output_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "image_dimensions": {"width": self.image_width, "height": self.image_height},
            "detection_count": self.detection_count,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "saved_output_path": self.saved_output_path,
            "detections": [d.to_dict() for d in self.detections],
        }


@dataclass
class TrafficDensityResult:
    """Estimated traffic density metrics."""
    level: str  # LOW, MEDIUM, HIGH
    vehicle_count: int
    congestion_index: float  # 0.0 to 1.0
    vehicles_by_type: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "density_level": self.level,
            "total_vehicles": self.vehicle_count,
            "congestion_index": round(self.congestion_index, 3),
            "vehicles_by_type": self.vehicles_by_type
        }


class CameraStream:
    """
    Hardware-accelerated camera stream with Auto-Exposure (AEC) and Auto-White Balance (AWB).
    Supports:
    1. Raspberry Pi 4/5 CSI Camera via Picamera2 (libcamera Bookworm stack).
    2. OpenCV V4L2 / USB camera with hardware property controls.
    3. Video file playback for testing and prototype demonstrations.
    """

    def __init__(
        self,
        source: Union[int, str] = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        enable_aec: bool = True,
        enable_awb: bool = True
    ):
        self.source = source
        self.width = width
        self.height = height
        self.target_fps = fps
        self.enable_aec = enable_aec
        self.enable_awb = enable_awb

        self.is_picamera = False
        self.picam2 = None
        self.cap = None
        self._is_video_file = isinstance(source, str) and not source.isdigit() and os.path.exists(source)

        self._init_capture()

    def _close_picamera(self):
        if self.picam2 is None:
            return
        try:
            self.picam2.stop()
        except Exception:
            pass
        try:
            self.picam2.close()
        except Exception:
            pass
        self.picam2 = None
        self.is_picamera = False

    def _try_picamera_config(self, Picamera2, size: Tuple[int, int], fmt: str) -> bool:
        """Configure IMX219 using a native sensor size. 1280x720 is not native and times out."""
        w, h = size
        self._close_picamera()
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"size": (w, h), "format": fmt},
            buffer_count=6,
        )
        self.picam2.configure(config)
        self.picam2.start()
        time.sleep(1.2)
        test = self.picam2.capture_array("main")
        if test is None or getattr(test, "size", 0) == 0:
            raise RuntimeError("empty CSI frame")
        self.is_picamera = True
        self._picamera_format = fmt
        logger.info(
            f"Picamera2 CSI active: {w}x{h} {fmt} (requested pipeline {self.width}x{self.height})"
        )
        return True

    def _init_capture(self):
        """Initialize camera backend with hardware AEC/AWB."""
        if not self._is_video_file:
            try:
                from picamera2 import Picamera2
                logger.info("Initializing Raspberry Pi CSI Camera via Picamera2 (libcamera)...")
                last_err = None
                # Native IMX219 modes only. 1280x720 causes frontend timeout.
                candidates = [
                    ((1920, 1080), "BGR888"),
                    ((1920, 1080), "RGB888"),
                    ((1640, 1232), "BGR888"),
                    ((1640, 1232), "RGB888"),
                    ((640, 480), "BGR888"),
                    ((640, 480), "RGB888"),
                ]
                for size, fmt in candidates:
                    try:
                        logger.info(f"Trying CSI mode {size[0]}x{size[1]} {fmt}...")
                        self._try_picamera_config(Picamera2, size, fmt)
                        try:
                            controls = {}
                            if self.enable_aec:
                                controls["AeEnable"] = True
                            if self.enable_awb:
                                controls["AwbEnable"] = True
                            if controls:
                                self.picam2.set_controls(controls)
                        except Exception:
                            pass
                        return
                    except Exception as e:
                        last_err = e
                        logger.warning(f"CSI mode {size[0]}x{size[1]} {fmt} failed: {e}")
                        self._close_picamera()
                raise RuntimeError(last_err or "All CSI modes failed")
            except ImportError:
                logger.warning(
                    "Picamera2 not installed. On Pi: sudo apt install -y python3-picamera2 "
                    "and set include-system-site-packages = true in venv/pyvenv.cfg"
                )
            except Exception as e:
                err_msg = str(e)
                if "busy" in err_msg.lower() or "acquire" in err_msg.lower():
                    logger.error(
                        f"Camera is already in use ({e}). Stop other camera apps:\n"
                        "  sudo killall -9 rpicam-hello rpicam-vid libcamera-vid python"
                    )
                else:
                    logger.warning(f"Picamera2 CSI init failed ({e}).")

        # 2. Fallback to OpenCV VideoCapture (V4L2, USB, GStreamer, or Video File)
        src_id = int(self.source) if (isinstance(self.source, int) or (isinstance(self.source, str) and self.source.isdigit())) else self.source
        logger.info(f"Opening OpenCV capture on source '{src_id}'...")

        # If on Linux and CSI camera is exposed via GStreamer:
        if isinstance(src_id, int) and sys.platform.startswith("linux"):
            # Try GStreamer libcamerasrc pipeline first on Linux
            gst_pipeline = (
                f"libcamerasrc ! video/x-raw, width={self.width}, height={self.height}, framerate={self.target_fps}/1 "
                f"! videoconvert ! appsink"
            )
            try:
                self.cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
                if self.cap.isOpened():
                    logger.info("✅ Opened CSI camera via GStreamer libcamerasrc pipeline.")
            except Exception:
                self.cap = None

        if self.cap is None or not self.cap.isOpened():
            if isinstance(src_id, int):
                self.cap = cv2.VideoCapture(src_id)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)

                # Hardware-level AEC and AWB controls in OpenCV V4L2
                if self.enable_aec:
                    try:
                        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)
                    except Exception:
                        pass
                if self.enable_awb:
                    try:
                        self.cap.set(cv2.CAP_PROP_AUTO_WB, 1)
                    except Exception:
                        pass
            else:
                self.cap = cv2.VideoCapture(src_id)

        if not self.cap or not self.cap.isOpened():
            if sys.platform.startswith("linux") and not self._is_video_file:
                raise RuntimeError(
                    "Raspberry Pi CSI camera timed out or failed to start.\n"
                    "Power OFF the Pi, reseat the camera ribbon on BOTH ends, power ON,\n"
                    "then run: rpicam-hello -t 3000\n"
                    "If that shows an image, retry: python -m ai.cli live --source 0 ..."
                )
            sample_candidates = [
                os.path.join(PROJECT_ROOT, "tfliterpipothole", "pothole1", "pothole1.mp4"),
                os.path.join(PROJECT_ROOT, "ai", "samples", "real_pothole_720p.mp4")
            ]
            for candidate in sample_candidates:
                if os.path.exists(candidate):
                    logger.warning(f"⚠️ Live camera not available. Automatically falling back to demo road video: {candidate}")
                    self.cap = cv2.VideoCapture(candidate)
                    self._is_video_file = True
                    break

        if not self.cap or not self.cap.isOpened():
            raise RuntimeError(
                f"Failed to open video source '{self.source}'.\n"
                "If on Raspberry Pi, ensure camera ribbon cable is firmly connected and run:\n"
                "     rpicam-hello --list-cameras"
            )

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS) or self.target_fps
        logger.info(f"✅ OpenCV VideoCapture opened successfully: {actual_w}x{actual_h} @ {actual_fps:.1f} FPS")

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read a single frame from the camera stream."""
        if self.is_picamera and self.picam2 is not None:
            try:
                frame = self.picam2.capture_array("main")
                if frame is not None and frame.size > 0:
                    if len(frame.shape) == 3 and frame.shape[2] == 3:
                        fmt = getattr(self, "_picamera_format", "RGB888")
                        if fmt.upper().startswith("RGB"):
                            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    if frame.shape[1] != self.width or frame.shape[0] != self.height:
                        frame = cv2.resize(frame, (self.width, self.height))
                    return True, frame
            except Exception as e:
                logger.error(f"Picamera2 capture error: {e}")
                return False, None

        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret and self._is_video_file:
                # Loop video file for continuous testing
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
            if ret and frame is not None:
                # Ensure 1280x720 standard
                if frame.shape[1] != self.width or frame.shape[0] != self.height:
                    frame = cv2.resize(frame, (self.width, self.height))
                return True, frame
            return False, None

        return False, None

    def release(self):
        """Cleanly release camera resources."""
        self._close_picamera()
        if self.cap is not None:
            self.cap.release()
        logger.info("Camera stream released.")


class AsyncVideoWriterWorker:
    """
    Background worker that writes incident video clips to disk asynchronously,
    preventing frame drops in the real-time 30 FPS inference pipeline.
    """

    def __init__(self, aggregator: CentralAggregator):
        self.aggregator = aggregator
        self.write_queue = queue.Queue(maxsize=10)
        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._run, daemon=True, name="AsyncVideoWriter")
        self.worker_thread.start()

    def submit_incident_clip(
        self,
        clip_frames: List[np.ndarray],
        incident_metadata: Dict[str, Any],
        output_filename: str,
        fps: int = 30,
        dimensions: Tuple[int, int] = (1280, 720)
    ):
        """Queue a 10-second HD incident clip for encoding and persistence."""
        try:
            self.write_queue.put_nowait({
                "frames": clip_frames,
                "metadata": incident_metadata,
                "filename": output_filename,
                "fps": fps,
                "dimensions": dimensions
            })
            logger.info(f"Queued incident clip '{output_filename}' ({len(clip_frames)} frames) for async writing.")
        except queue.Full:
            logger.warning("Video writer queue is full. Dropping older video clip to prevent memory starvation.")

    def _run(self):
        while not self.stop_event.is_set():
            try:
                task = self.write_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            frames = task["frames"]
            metadata = task["metadata"]
            out_path = task["filename"]
            fps = task["fps"]
            width, height = task["dimensions"]

            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            logger.info(f"Writing {len(frames)} frames to HD video file '{out_path}'...")

            t0 = time.perf_counter()
            # Try H264 codec first, fallback to mp4v
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(out_path, fourcc, float(fps), (width, height))

            if not writer.isOpened():
                logger.error(f"Failed to open cv2.VideoWriter for '{out_path}'")
                self.write_queue.task_done()
                continue

            for frame in frames:
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(frame, (width, height))
                writer.write(frame)

            writer.release()
            elapsed = time.perf_counter() - t0
            file_size_mb = os.path.getsize(out_path) / (1024 * 1024) if os.path.exists(out_path) else 0.0
            logger.info(f"✅ Incident video clip saved: '{out_path}' ({file_size_mb:.2f} MB in {elapsed:.2f}s)")

            # Dispatch incident metadata and video reference via Aggregator
            try:
                incident_payload = self.aggregator.package_incident(
                    defect_type=metadata.get("defect_type", "POTHOLE"),
                    confidence=metadata.get("confidence", 0.85),
                    bbox=metadata.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                    estimated_size_sqm=metadata.get("estimated_size_sqm", 0.35),
                    video_clip_path=out_path,
                    traffic_density_data=metadata.get("traffic_density"),
                    gps_override=metadata.get("gps"),
                    camera_specs={"resolution": f"{width}x{height}", "fps": fps, "aec_enabled": True, "awb_enabled": True}
                )
                self.aggregator.transmit_incident(incident_payload, video_clip_path=out_path)
            except Exception as e:
                logger.error(f"Failed to package/transmit incident: {e}")

            self.write_queue.task_done()

    def stop(self):
        """Stop worker thread."""
        self.stop_event.set()
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3.0)


class CircularFrameBuffer:
    """
    Thread-safe circular frame buffer utilizing Python's collections.deque.
    Maintains a rolling 5-second pre-event history (150 frames @ 30 FPS).
    Upon trigger, accumulates 5 post-event seconds (150 frames @ 30 FPS)
    for a total 10-second (300 frames) HD incident recording.
    """

    def __init__(
        self,
        fps: int = 30,
        pre_event_seconds: float = 5.0,
        post_event_seconds: float = 5.0,
        cooldown_seconds: float = 8.0,
        writer_worker: Optional[AsyncVideoWriterWorker] = None,
        captures_dir: str = DEFAULT_CAPTURES_DIR
    ):
        self.fps = fps
        self.pre_event_frames_target = int(pre_event_seconds * fps)    # 150 frames
        self.post_event_frames_target = int(post_event_seconds * fps)  # 150 frames
        self.cooldown_seconds = cooldown_seconds
        self.writer_worker = writer_worker
        self.captures_dir = captures_dir

        self.lock = threading.Lock()
        # Thread-safe rolling pre-event buffer
        self.pre_event_buffer = deque(maxlen=self.pre_event_frames_target)

        # Active incident recording state
        self.is_recording = False
        self.post_event_buffer: List[np.ndarray] = []
        self.current_pre_event_snapshot: List[np.ndarray] = []
        self.current_metadata: Optional[Dict[str, Any]] = None
        self.last_trigger_time: float = 0.0

    def push_frame(self, frame: np.ndarray) -> bool:
        """
        Push incoming frame into rolling buffer and manage post-event capture if triggered.
        Returns True if a full 10s incident clip was completed on this frame.
        """
        with self.lock:
            # 1. Always update rolling pre-event buffer when not mid-event
            self.pre_event_buffer.append(frame.copy())

            # 2. If an incident recording is active, accumulate post-event frames
            if self.is_recording:
                self.post_event_buffer.append(frame.copy())

                if len(self.post_event_buffer) >= self.post_event_frames_target:
                    # Completed 5-second post-event window!
                    full_clip = self.current_pre_event_snapshot + self.post_event_buffer
                    clip_metadata = self.current_metadata or {}

                    # Generate output filename
                    ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    short_id = str(uuid.uuid4())[:8]
                    out_filename = os.path.join(self.captures_dir, f"pothole_event_{ts_str}_{short_id}.mp4")

                    # Reset recording state
                    self.is_recording = False
                    self.post_event_buffer = []
                    self.current_pre_event_snapshot = []
                    self.current_metadata = None

                    # Dispatch to asynchronous background writer
                    if self.writer_worker:
                        self.writer_worker.submit_incident_clip(
                            clip_frames=full_clip,
                            incident_metadata=clip_metadata,
                            output_filename=out_filename,
                            fps=self.fps,
                            dimensions=(frame.shape[1], frame.shape[0])
                        )
                    return True

        return False

    def trigger_incident(self, metadata: Dict[str, Any]) -> bool:
        """
        Trigger an incident recording event upon detecting a valid pothole (conf >= 0.75).
        Enforces cooldown to prevent overlapping clips for the same physical road defect.
        """
        now = time.time()
        with self.lock:
            # Enforce cooldown period
            if (now - self.last_trigger_time) < self.cooldown_seconds:
                return False

            if self.is_recording:
                return False

            self.is_recording = True
            self.last_trigger_time = now
            self.current_metadata = metadata
            # Snapshot the current 5-second pre-event history
            self.current_pre_event_snapshot = list(self.pre_event_buffer)
            self.post_event_buffer = []

            logger.info(
                f"🚨 Pothole Incident Triggered! Pre-event history: {len(self.current_pre_event_snapshot)} frames "
                f"(~{len(self.current_pre_event_snapshot) / self.fps:.1f}s). Recording 5 post-event seconds..."
            )
            return True


class PotholeDetector:
    """
    High-Performance Edge Detector Engine.
    Executes Pothole Detection (strict conf >= 0.75) and Traffic Density Monitoring.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        pothole_model_path: Optional[str] = None,
        vehicle_model_path: str = DEFAULT_VEHICLE_MODEL,
        conf_threshold: Optional[float] = None,
        confidence_threshold: Optional[float] = None,
        pothole_conf: float = 0.75,
        traffic_conf: float = 0.35,
        device: str = "cpu",
        require_pothole_class: bool = True
    ):
        actual_path = model_path or pothole_model_path or DEFAULT_POTHOLE_MODEL
        actual_conf = conf_threshold if conf_threshold is not None else (confidence_threshold if confidence_threshold is not None else pothole_conf)

        self.model_path = actual_path
        self.conf_threshold = actual_conf
        self.pothole_conf = actual_conf
        self.traffic_conf = traffic_conf
        self.device = device

        validate_system_directories()

        self.is_tflite = actual_path.lower().endswith(".tflite")
        self.is_onnx = False
        self.is_cv_dnn = False
        self.onnx_session = None
        self.cv_net = None
        self.tflite_interpreter = None
        self.pothole_model = None
        self.model = None
        self.onnx_imgsz = (640, 640)

        if self.is_tflite:
            logger.info(f"Loading TensorFlow Lite model from '{actual_path}'...")
            try:
                import tflite_runtime.interpreter as tflite
                self.tflite_interpreter = tflite.Interpreter(model_path=actual_path)
            except ImportError:
                import tensorflow as tf
                self.tflite_interpreter = tf.lite.Interpreter(model_path=actual_path)
            self.tflite_interpreter.allocate_tensors()
            self.tflite_input_details = self.tflite_interpreter.get_input_details()
            self.tflite_output_details = self.tflite_interpreter.get_output_details()
            self.pothole_model = None
            self.model = None
            self.pothole_class_names = {0: "pothole"}
            self.class_names = self.pothole_class_names
            logger.info(f"TFLite model loaded successfully: Inputs: {self.tflite_input_details[0]['shape']}")

        elif not _ULTRALYTICS_AVAILABLE:
            onnx_path = actual_path
            if actual_path.lower().endswith(".pt"):
                onnx_path = actual_path[:-3] + ".onnx"
            if not os.path.exists(onnx_path):
                raise FileNotFoundError(
                    f"ONNX model not found at '{onnx_path}'.\n"
                    "On your PC: yolo export model=ai/models/pothole_model.pt format=onnx imgsz=640 simplify=True\n"
                    "Then copy pothole_model.onnx to the Pi: ai/models/"
                )

            self.pothole_class_names = {0: "pothole"}
            self.class_names = self.pothole_class_names

            if _ONNX_AVAILABLE and _ort is not None:
                logger.info(f"Loading ONNX model from '{onnx_path}' via onnxruntime...")
                self.onnx_session = _ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
                self.onnx_input_name = self.onnx_session.get_inputs()[0].name
                self.onnx_input_shape = self.onnx_session.get_inputs()[0].shape
                self.onnx_imgsz = (
                    self.onnx_input_shape[2] if isinstance(self.onnx_input_shape[2], int) else 640,
                    self.onnx_input_shape[3] if isinstance(self.onnx_input_shape[3], int) else 640,
                )
                self.is_onnx = True
                logger.info(
                    f"ONNX Runtime loaded. Input: {self.onnx_input_name} shape={self.onnx_input_shape}. "
                    f"Conf threshold: {self.pothole_conf}"
                )
            else:
                logger.info(f"Loading ONNX model from '{onnx_path}' via OpenCV DNN (no onnxruntime/ultralytics)...")
                self.cv_net = cv2.dnn.readNetFromONNX(onnx_path)
                self.cv_net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.cv_net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self.onnx_imgsz = (640, 640)
                self.is_cv_dnn = True
                logger.info(f"OpenCV DNN loaded. Conf threshold: {self.pothole_conf}")

        else:
            logger.info(f"Loading pothole YOLO model from '{actual_path}' on device '{device}'...")
            if not os.path.exists(actual_path):
                raise FileNotFoundError(
                    f"Pothole model weights file not found at '{actual_path}'. "
                    "Please ensure the fine-tuned custom weights file exists."
                )

            self.pothole_model = YOLO(actual_path)
            self.model = self.pothole_model
            self.pothole_class_names = self.pothole_model.names if hasattr(self.pothole_model, "names") else {}
            self.class_names = self.pothole_class_names
            logger.info(f"Pothole model loaded. Class mapping: {self.pothole_class_names}. Strict Conf Threshold: {self.pothole_conf}")

            # Validate that model is not generic COCO model
            if require_pothole_class:
                if len(self.pothole_class_names) == 80 and self.pothole_class_names.get(0) == "person":
                    raise ValueError(
                        f"Model at '{actual_path}' is a generic COCO dataset model (80 classes: person, car, dog...). "
                        "Arbitrary class remapping of generic COCO models to potholes is strictly prohibited. "
                        "Please provide an authentic pothole-trained YOLO model."
                    )

        # 2. Load Vehicle YOLO Model for Traffic Density Monitoring
        self.vehicle_model = None
        self.vehicle_classes = ["car", "bus", "truck", "motorcycle"]
        self.vehicle_class_indices = []

        if YOLO is not None and os.path.exists(vehicle_model_path):
            try:
                logger.info(f"Loading vehicle detection model from '{vehicle_model_path}'...")
                self.vehicle_model = YOLO(vehicle_model_path)
                names = self.vehicle_model.names or {}
                self.vehicle_class_indices = [
                    idx for idx, name in names.items()
                    if str(name).lower() in self.vehicle_classes
                ]
                logger.info(f"Traffic density detector ready. Vehicle indices: {self.vehicle_class_indices}")
            except Exception as e:
                logger.warning(f"Could not load vehicle model: {e}. Traffic density will run in simulated mode.")
        elif YOLO is not None:
            logger.info("Vehicle model not present at path. Loading standard yolov8n.pt...")
            try:
                self.vehicle_model = YOLO("yolov8n.pt")
                names = self.vehicle_model.names or {}
                self.vehicle_class_indices = [
                    idx for idx, name in names.items()
                    if str(name).lower() in self.vehicle_classes
                ]
            except Exception as e:
                logger.warning(f"Failed to initialize vehicle detector: {e}")
        else:
            logger.info("Ultralytics not installed — traffic density runs in simulated mode (Pi/OpenCV DNN mode).")

    def _decode_yolo_onnx(
        self,
        pred: np.ndarray,
        img_w: int,
        img_h: int,
        in_w: int,
        in_h: int,
        conf: float,
        total_area: float,
    ) -> List[PotholeDetection]:
        """Decode YOLOv8 ONNX output (num_classes+4, 8400) into pothole boxes."""
        detections: List[PotholeDetection] = []
        if pred.ndim == 3:
            pred = pred[0]
        boxes_raw = pred[:4, :].T
        scores_raw = pred[4:, :].T
        if scores_raw.ndim == 1:
            scores_raw = scores_raw.reshape(-1, 1)
        class_ids = np.argmax(scores_raw, axis=1)
        confidences = scores_raw[np.arange(len(scores_raw)), class_ids]
        mask = confidences >= conf
        boxes_raw = boxes_raw[mask]
        confidences = confidences[mask]
        class_ids = class_ids[mask]
        if len(boxes_raw) == 0:
            return detections

        cx, cy, bw, bh = boxes_raw[:, 0], boxes_raw[:, 1], boxes_raw[:, 2], boxes_raw[:, 3]
        x1 = (cx - bw / 2) * (img_w / in_w)
        y1 = (cy - bh / 2) * (img_h / in_h)
        x2 = (cx + bw / 2) * (img_w / in_w)
        y2 = (cy + bh / 2) * (img_h / in_h)
        nms_boxes = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
        indices = cv2.dnn.NMSBoxes(nms_boxes, confidences.tolist(), score_threshold=float(conf), nms_threshold=0.45)
        if len(indices) == 0:
            return detections
        indices = [
            i[0] if isinstance(i, (list, tuple, np.ndarray)) else int(i)
            for i in (indices.flatten() if hasattr(indices, "flatten") else indices)
        ]
        for idx in indices:
            bbox = BoundingBox(
                x_min=max(0.0, float(x1[idx])),
                y_min=max(0.0, float(y1[idx])),
                x_max=min(float(img_w), float(x2[idx])),
                y_max=min(float(img_h), float(y2[idx])),
            )
            area_ratio = bbox.area_px / total_area if total_area > 0 else 0.0
            detections.append(PotholeDetection(
                class_id=int(class_ids[idx]),
                class_name="pothole",
                confidence=float(confidences[idx]),
                bbox=bbox,
                area_ratio=area_ratio,
            ))
        return detections

    def detect_potholes(self, frame: np.ndarray, conf_threshold: Optional[float] = None) -> List[PotholeDetection]:
        """
        Run inference on frame with strict confidence threshold (default 0.75).
        Supports both PyTorch YOLO and TensorFlow Lite models.
        """
        conf = conf_threshold if conf_threshold is not None else self.pothole_conf
        img_h, img_w = frame.shape[:2]
        total_area = img_h * img_w
        detections: List[PotholeDetection] = []

        if getattr(self, "is_tflite", False) and self.tflite_interpreter is not None:
            # TFLite Inference Execution
            input_shape = self.tflite_input_details[0]['shape']
            in_h, in_w = input_shape[1], input_shape[2]
            input_data = cv2.resize(frame, (in_w, in_h))
            input_data = cv2.cvtColor(input_data, cv2.COLOR_BGR2RGB)
            if self.tflite_input_details[0]['dtype'] == np.float32:
                input_data = (input_data.astype(np.float32) - 127.5) / 127.5
            input_data = np.expand_dims(input_data, axis=0)

            self.tflite_interpreter.set_tensor(self.tflite_input_details[0]['index'], input_data)
            self.tflite_interpreter.invoke()

            boxes = self.tflite_interpreter.get_tensor(self.tflite_output_details[0]['index'])[0]
            classes = self.tflite_interpreter.get_tensor(self.tflite_output_details[1]['index'])[0]
            scores = self.tflite_interpreter.get_tensor(self.tflite_output_details[2]['index'])[0]
            num_det = int(self.tflite_interpreter.get_tensor(self.tflite_output_details[3]['index'])[0])

            for i in range(min(num_det, len(scores))):
                score = float(scores[i])
                if score >= conf:
                    box = boxes[i]
                    ymin, xmin, ymax, xmax = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                    bbox = BoundingBox(
                        x_min=max(0.0, xmin * img_w),
                        y_min=max(0.0, ymin * img_h),
                        x_max=min(float(img_w), xmax * img_w),
                        y_max=min(float(img_h), ymax * img_h)
                    )
                    area_ratio = bbox.area_px / total_area if total_area > 0 else 0.0
                    detections.append(PotholeDetection(
                        class_id=int(classes[i]),
                        class_name="pothole",
                        confidence=score,
                        bbox=bbox,
                        area_ratio=area_ratio
                    ))
            return detections

        if getattr(self, "is_onnx", False) and self.onnx_session is not None:
            in_h, in_w = self.onnx_imgsz
            resized = cv2.resize(frame, (in_w, in_h))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            blob = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)[np.newaxis, :]
            outputs = self.onnx_session.run(None, {self.onnx_input_name: blob})
            return self._decode_yolo_onnx(outputs[0], img_w, img_h, in_w, in_h, conf, total_area)

        if getattr(self, "is_cv_dnn", False) and self.cv_net is not None:
            in_h, in_w = self.onnx_imgsz
            blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (in_w, in_h), swapRB=True, crop=False)
            self.cv_net.setInput(blob)
            pred = self.cv_net.forward()
            return self._decode_yolo_onnx(pred, img_w, img_h, in_w, in_h, conf, total_area)

        results = self.pothole_model.predict(
            source=frame,
            conf=conf,
            device=self.device,
            verbose=False
        )

        if len(results) > 0 and results[0].boxes is not None:
            for box in results[0].boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                score = float(box.conf[0].cpu().numpy())
                cls_idx = int(box.cls[0].cpu().numpy())

                raw_name = self.pothole_class_names.get(cls_idx, f"class_{cls_idx}")
                cls_name = "pothole" if str(raw_name).lower() in ("0", "pothole") else str(raw_name)

                bbox = BoundingBox(x_min=float(xyxy[0]), y_min=float(xyxy[1]), x_max=float(xyxy[2]), y_max=float(xyxy[3]))
                area_ratio = bbox.area_px / total_area if total_area > 0 else 0.0

                detections.append(PotholeDetection(
                    class_id=cls_idx,
                    class_name=cls_name,
                    confidence=score,
                    bbox=bbox,
                    area_ratio=area_ratio
                ))

        return detections

    def set_confidence_threshold(self, conf_threshold: float):
        """Update confidence threshold dynamically."""
        if not (0.0 <= conf_threshold <= 1.0):
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        self.conf_threshold = conf_threshold
        self.pothole_conf = conf_threshold

    def predict_image(
        self,
        image_input: Union[str, np.ndarray],
        conf_threshold: Optional[float] = None,
        save_path: Optional[str] = None,
        draw_annotations: bool = True
    ) -> FrameDetectionResult:
        """Run pothole detection on a single image and return FrameDetectionResult."""
        conf = conf_threshold if conf_threshold is not None else self.conf_threshold
        if isinstance(image_input, str):
            source_name = os.path.basename(image_input)
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Image file not found: {image_input}")
            img_bgr = cv2.imread(image_input)
            if img_bgr is None:
                raise ValueError(f"Could not decode image at '{image_input}'")
        elif isinstance(image_input, np.ndarray):
            source_name = "numpy_array"
            img_bgr = image_input.copy()
        else:
            raise TypeError("image_input must be a file path string or numpy array")

        img_h, img_w = img_bgr.shape[:2]
        t0 = time.perf_counter()
        detections = self.detect_potholes(img_bgr, conf_threshold=conf)
        inference_time_ms = (time.perf_counter() - t0) * 1000.0

        annotated_img = img_bgr.copy() if draw_annotations else None
        if draw_annotations and annotated_img is not None:
            for d in detections:
                pt1 = (int(d.bbox.x_min), int(d.bbox.y_min))
                pt2 = (int(d.bbox.x_max), int(d.bbox.y_max))
                cv2.rectangle(annotated_img, pt1, pt2, (0, 0, 255), 2)
                label = f"{d.class_name.upper()}: {d.confidence:.2f}"
                cv2.putText(annotated_img, label, (pt1[0], max(15, pt1[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        saved_file_path = None
        if save_path and annotated_img is not None:
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            cv2.imwrite(save_path, annotated_img)
            saved_file_path = save_path

        return FrameDetectionResult(
            source=source_name,
            image_height=img_h,
            image_width=img_w,
            detection_count=len(detections),
            detections=detections,
            inference_time_ms=inference_time_ms,
            annotated_image=annotated_img,
            saved_output_path=saved_file_path
        )

    def predict_video(
        self,
        video_path: Union[str, int],
        output_path: Optional[str] = None,
        conf_threshold: Optional[float] = None,
        max_frames: Optional[int] = None,
        frame_callback=None
    ) -> Dict[str, Any]:
        """Process video and return summary."""
        cap = cv2.VideoCapture(int(video_path) if str(video_path).isdigit() else video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video source at '{video_path}'")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        writer = None
        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        frame_idx = 0
        total_detections = 0
        t0 = time.perf_counter()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            if max_frames and frame_idx > max_frames:
                break

            res = self.predict_image(frame, conf_threshold=conf_threshold, draw_annotations=(writer is not None))
            total_detections += res.detection_count
            if writer is not None and res.annotated_image is not None:
                writer.write(res.annotated_image)
            if frame_callback is not None:
                frame_callback(frame_idx, res)

        cap.release()
        if writer is not None:
            writer.release()

        elapsed = time.perf_counter() - t0
        return {
            "source_video": str(video_path),
            "output_video": output_path,
            "processed_frames": frame_idx,
            "total_detections": total_detections,
            "elapsed_seconds": round(elapsed, 2),
            "average_fps": round(frame_idx / elapsed if elapsed > 0 else 0.0, 2)
        }


    def estimate_traffic_density(self, frame: np.ndarray) -> TrafficDensityResult:
        """
        Detect vehicles and compute traffic density status (LOW, MEDIUM, HIGH) and congestion index.
        """
        if self.vehicle_model is None:
            # Return baseline estimate
            return TrafficDensityResult(level="LOW", vehicle_count=0, congestion_index=0.05, vehicles_by_type={})

        results = self.vehicle_model.predict(
            source=frame,
            conf=self.traffic_conf,
            classes=self.vehicle_class_indices if self.vehicle_class_indices else None,
            device=self.device,
            verbose=False
        )

        vehicle_counts: Dict[str, int] = {}
        total_vehicles = 0

        if len(results) > 0 and results[0].boxes is not None:
            for box in results[0].boxes:
                cls_idx = int(box.cls[0].cpu().numpy())
                v_name = str(self.vehicle_model.names.get(cls_idx, "vehicle")).lower()
                vehicle_counts[v_name] = vehicle_counts.get(v_name, 0) + 1
                total_vehicles += 1

        # Classify density level
        if total_vehicles <= 2:
            density_level = "LOW"
            congestion_index = min(1.0, total_vehicles * 0.15)
        elif total_vehicles <= 6:
            density_level = "MEDIUM"
            congestion_index = 0.35 + (total_vehicles - 2) * 0.12
        else:
            density_level = "HIGH"
            congestion_index = min(1.0, 0.75 + (total_vehicles - 6) * 0.05)

        return TrafficDensityResult(
            level=density_level,
            vehicle_count=total_vehicles,
            congestion_index=round(congestion_index, 3),
            vehicles_by_type=vehicle_counts
        )

    def draw_hud(
        self,
        frame: np.ndarray,
        potholes: List[PotholeDetection],
        traffic: TrafficDensityResult,
        is_recording: bool,
        fps_actual: float
    ) -> np.ndarray:
        """Render informative HUD overlay on frame."""
        annotated = frame.copy()
        h, w = frame.shape[:2]

        # 1. Draw Pothole Bounding Boxes
        for p in potholes:
            pt1 = (int(p.bbox.x_min), int(p.bbox.y_min))
            pt2 = (int(p.bbox.x_max), int(p.bbox.y_max))
            cv2.rectangle(annotated, pt1, pt2, (0, 0, 255), 2)

            label = f"POTHOLE: {p.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(annotated, (pt1[0], max(0, pt1[1] - th - 8)), (pt1[0] + tw + 8, pt1[1]), (0, 0, 255), -1)
            cv2.putText(annotated, label, (pt1[0] + 4, pt1[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # 2. Draw Top Status Banner
        cv2.rectangle(annotated, (10, 10), (w - 10, 50), (20, 20, 20), -1)
        cv2.rectangle(annotated, (10, 10), (w - 10, 50), (60, 60, 60), 1)

        # Traffic Density HUD
        traffic_colors = {"LOW": (0, 220, 0), "MEDIUM": (0, 180, 255), "HIGH": (0, 0, 255)}
        t_color = traffic_colors.get(traffic.level, (200, 200, 200))
        hud_left = f"TRAFFIC: {traffic.level} ({traffic.vehicle_count} veh) | CONGESTION: {int(traffic.congestion_index*100)}%"
        cv2.putText(annotated, hud_left, (25, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.6, t_color, 2, cv2.LINE_AA)

        # FPS & Recording Indicator HUD
        rec_str = "● RECORDING EVENT" if is_recording else "MONITORING"
        rec_col = (0, 0, 255) if is_recording else (0, 255, 0)
        hud_right = f"FPS: {fps_actual:.1f} | 1280x720 | {rec_str}"
        (rw, _), _ = cv2.getTextSize(hud_right, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.putText(annotated, hud_right, (w - rw - 25, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.55, rec_col, 2, cv2.LINE_AA)

        return annotated


class JpegFrameHub:
    """Latest annotated JPEG for the Pi MJPEG preview server."""

    def __init__(self):
        self.lock = threading.Lock()
        self.jpeg: Optional[bytes] = None

    def publish_bgr(self, frame: np.ndarray):
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ok:
            with self.lock:
                self.jpeg = buf.tobytes()

    def get_jpeg(self) -> Optional[bytes]:
        with self.lock:
            return self.jpeg


class _MjpegHandler(BaseHTTPRequestHandler):
    hub: Optional[JpegFrameHub] = None

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/", "/video_feed"):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while True:
                jpeg = self.hub.get_jpeg() if self.hub else None
                if jpeg:
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
                time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, format, *args):
        return


class ThreadedMjpegServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class EdgePerceptionPipeline:
    """
    Main Orchestrator for the Edge Sensing Node.
    Connects CameraStream, CircularFrameBuffer, PotholeDetector, and CentralAggregator.
    """

    def __init__(
        self,
        camera_source: Union[int, str] = 0,
        resolution: Tuple[int, int] = (1280, 720),
        fps: int = 30,
        pothole_conf: float = 0.75,
        traffic_conf: float = 0.35,
        pothole_model_path: str = DEFAULT_POTHOLE_MODEL,
        backend_url: str = "http://192.168.1.100:8000/api/v1/incidents",
        auth_token: str = "sih_admin",
        device_id: str = "EDGE-RPI4-001",
        enable_display: bool = False,
        stream_port: int = 5001,
    ):
        self.width, self.height = resolution
        self.fps = fps
        self.enable_display = enable_display
        self.stream_port = stream_port
        self.stop_event = threading.Event()
        self.frame_hub = JpegFrameHub()
        self._mjpeg_httpd = None

        # 1. Central Aggregator
        self.aggregator = CentralAggregator(
            backend_url=backend_url,
            auth_token=auth_token,
            device_id=device_id
        )

        # 2. Async Video Writer Worker
        self.writer_worker = AsyncVideoWriterWorker(aggregator=self.aggregator)

        # 3. Thread-Safe Circular Frame Buffer (5s pre + 5s post = 10s @ 30 FPS)
        self.frame_buffer = CircularFrameBuffer(
            fps=self.fps,
            pre_event_seconds=5.0,
            post_event_seconds=5.0,
            cooldown_seconds=8.0,
            writer_worker=self.writer_worker,
            captures_dir=DEFAULT_CAPTURES_DIR
        )

        # 4. Detector Engine
        self.detector = PotholeDetector(
            pothole_model_path=pothole_model_path,
            pothole_conf=pothole_conf,
            traffic_conf=traffic_conf
        )

        # 5. Camera Stream with hardware AEC/AWB
        self.camera = CameraStream(
            source=camera_source,
            width=self.width,
            height=self.height,
            fps=self.fps,
            enable_aec=True,
            enable_awb=True
        )

        if self.stream_port and self.stream_port > 0:
            self._start_mjpeg_server()

        logger.info(
            f"EdgePerceptionPipeline fully initialized. Resolution: {self.width}x{self.height} @ {self.fps} FPS, "
            f"Strict Conf: {pothole_conf}, Target Backend: {backend_url}, MJPEG :{self.stream_port}"
        )

    def _start_mjpeg_server(self):
        _MjpegHandler.hub = self.frame_hub
        try:
            self._mjpeg_httpd = ThreadedMjpegServer(("0.0.0.0", self.stream_port), _MjpegHandler)
            threading.Thread(target=self._mjpeg_httpd.serve_forever, daemon=True, name="MjpegPreview").start()
            logger.info(f"Pi camera preview: http://0.0.0.0:{self.stream_port}/video_feed")
        except OSError as e:
            logger.warning(f"Could not bind MJPEG preview port {self.stream_port}: {e}")
            self._mjpeg_httpd = None

    def run(self, max_frames: Optional[int] = None):
        """Execute real-time edge processing loop."""
        logger.info("Starting Edge Perception Loop. Press Ctrl+C to terminate.")
        frame_idx = 0
        t_start = time.perf_counter()
        last_fps_time = time.perf_counter()
        fps_counter = 0
        actual_fps = float(self.fps)

        # Traffic density estimation throttler (every 5 frames to conserve edge CPU)
        last_traffic_result = TrafficDensityResult(level="LOW", vehicle_count=0, congestion_index=0.0, vehicles_by_type={})

        try:
            while not self.stop_event.is_set():
                ret, frame = self.camera.read_frame()
                if not ret or frame is None:
                    logger.warning("Camera stream returned empty frame. Pausing briefly...")
                    time.sleep(0.05)
                    continue

                frame_idx += 1
                fps_counter += 1

                # Calculate smoothed live FPS every 30 frames
                if fps_counter >= 30:
                    now = time.perf_counter()
                    actual_fps = fps_counter / (now - last_fps_time)
                    fps_counter = 0
                    last_fps_time = now

                # 1. Estimate Traffic Density periodically
                if frame_idx % 5 == 0:
                    last_traffic_result = self.detector.estimate_traffic_density(frame)

                # 2. Run Pothole Detection with strict threshold (>= 0.75)
                potholes = self.detector.detect_potholes(frame)

                # 3. Check for valid anomaly trigger
                if len(potholes) > 0:
                    best_pothole = max(potholes, key=lambda p: p.confidence)
                    if best_pothole.confidence >= self.detector.pothole_conf:
                        # Prepare incident metadata
                        incident_metadata = {
                            "defect_type": "POTHOLE",
                            "confidence": best_pothole.confidence,
                            "bbox": best_pothole.bbox.to_list(),
                            "estimated_size_sqm": round(best_pothole.area_ratio * 20.0, 4),
                            "traffic_density": last_traffic_result.to_dict(),
                            "gps": self.aggregator.gps_provider.get_coordinates()
                        }
                        self.frame_buffer.trigger_incident(metadata=incident_metadata)

                # 4. Push frame to circular frame buffer
                self.frame_buffer.push_frame(frame)

                # 5. Optional GUI display for development / demonstration
                hud_frame = self.detector.draw_hud(
                    frame=frame,
                    potholes=potholes,
                    traffic=last_traffic_result,
                    is_recording=self.frame_buffer.is_recording,
                    fps_actual=actual_fps
                )
                self.frame_hub.publish_bgr(hud_frame)

                if self.enable_display:
                    cv2.imshow("SIH26124 - Edge Road Intelligence", hud_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        logger.info("User requested exit via 'q' key.")
                        break

                if max_frames and frame_idx >= max_frames:
                    logger.info(f"Reached specified frame limit ({max_frames}). Stopping loop.")
                    break

        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt. Shutting down pipeline cleanly...")
        finally:
            self.shutdown()

    def shutdown(self):
        """Clean resource shutdown."""
        self.stop_event.set()
        if self._mjpeg_httpd is not None:
            try:
                self._mjpeg_httpd.shutdown()
            except Exception:
                pass
        self.camera.release()
        self.writer_worker.stop()
        self.aggregator.stop()
        if self.enable_display:
            cv2.destroyAllWindows()
        logger.info("Edge Perception Pipeline shutdown complete.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SIH26124 Edge Road Intelligence & Circular Buffer Capture")
    parser.add_argument("--source", type=str, default="0", help="Camera index (0) or video file path")
    parser.add_argument("--conf", type=float, default=0.75, help="Strict pothole confidence threshold (default: 0.75)")
    parser.add_argument("--backend-url", type=str, default="http://192.168.1.100:8000/api/v1/incidents", help="Municipal backend REST API")
    parser.add_argument("--token", type=str, default="sih_admin", help="Bearer authentication token")
    parser.add_argument("--display", action="store_true", help="Enable OpenCV GUI preview window")
    parser.add_argument("--max-frames", type=int, default=None, help="Maximum frames to process")
    args = parser.parse_args()

    pipeline = EdgePerceptionPipeline(
        camera_source=args.source,
        pothole_conf=args.conf,
        backend_url=args.backend_url,
        auth_token=args.token,
        enable_display=args.display
    )
    pipeline.run(max_frames=args.max_frames)
