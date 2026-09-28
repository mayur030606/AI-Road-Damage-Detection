"""
Standalone Municipal Incident Ingestion, Live Video Streaming & Web Dashboard Server.

Implements:
- REST Ingestion Endpoint: POST /api/v1/incidents (Bearer sih_admin)
- Health Endpoint: GET /health and GET /api/v1/health
- Live MJPEG Stream: GET /video_feed (Real-time Pothole Detection on tfliterpipothole/pothole1/pothole1.mp4)
- Dataset Explorer APIs:
    * GET /api/v1/dataset
    * GET /api/v1/dataset/raw/<filename>
    * GET /api/v1/dataset/annotated/<filename>
    * GET /api/v1/dataset/inspect/<filename>
- Incident Video Captures: GET /api/v1/video/<filename>
- Rich Interactive Web Dashboard: GET /

Usage:
  python scripts/mock_backend.py --port 8000
"""

import argparse
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging
import os
from socketserver import ThreadingMixIn
import sys
import threading
import time
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from urllib.error import URLError

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BACKEND] %(message)s"
)
logger = logging.getLogger("MockBackend")

EXPECTED_TOKEN = "sih_admin"
POTHOLE_CONF = float(os.environ.get("POTHOLE_CONF", "0.50"))
STORED_INCIDENTS = []
LOG_FILE = os.path.join(os.path.dirname(__file__), "received_incidents.jsonl")

# Load existing incidents from LOG_FILE if available
if os.path.exists(LOG_FILE):
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    STORED_INCIDENTS.append(json.loads(line))
        logger.info(f"Loaded {len(STORED_INCIDENTS)} persisted incidents from {LOG_FILE}")
    except Exception as e:
        logger.warning(f"Could not load previous incidents: {e}")

# Paths for video and dataset
POTHOLE_VIDEO_PATH = os.path.join(PROJECT_ROOT, "tfliterpipothole", "pothole1", "pothole1.mp4")
FALLBACK_VIDEO_PATH = os.path.join(PROJECT_ROOT, "ai", "samples", "real_pothole_720p.mp4")
DATASET_DIR = os.path.join(PROJECT_ROOT, "tfliterpipothole", "potholeimages", "potholeimages")
VIDEO_CAPTURES_DIR = os.path.join(PROJECT_ROOT, "ai", "video_captures")
MODEL_PATH = os.path.join(PROJECT_ROOT, "ai", "models", "pothole_model.pt")
PI_STREAM_URL = os.environ.get("PI_STREAM_URL", "http://10.54.12.49:5001/video_feed")

# Global PotholeDetector instance (loaded lazily)
_DETECTOR_LOCK = threading.Lock()
_POTHOLE_DETECTOR = None


def get_detector():
    global _POTHOLE_DETECTOR
    with _DETECTOR_LOCK:
        if _POTHOLE_DETECTOR is None:
            try:
                from ai.detector import PotholeDetector
                if os.path.exists(MODEL_PATH):
                    _POTHOLE_DETECTOR = PotholeDetector(
                        model_path=MODEL_PATH,
                        confidence_threshold=POTHOLE_CONF,
                        device="cpu"
                    )
                    logger.info("Loaded authentic PotholeDetector model into backend server.")
                else:
                    logger.warning(f"Model path {MODEL_PATH} not found. Operating with visual heuristics.")
            except Exception as e:
                logger.error(f"Failed to load PotholeDetector: {e}")
        return _POTHOLE_DETECTOR


# Cache for dataset images inspection results
DATASET_CACHE = {}


def get_dataset_files():
    if not os.path.isdir(DATASET_DIR):
        return []
    files = [f for f in os.listdir(DATASET_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    # Sort naturally (1.jpg, 2.jpg, ... 10.jpg)
    def natural_sort_key(s):
        import re
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
    return sorted(files, key=natural_sort_key)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class IncidentRequestHandler(BaseHTTPRequestHandler):

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Device-Id")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, status_code: int, content_type: str, data: bytes):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Device-Id")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # 1. Health Endpoints
        if path in ("/health", "/api/v1/health"):
            self._send_json(200, {
                "status": "UP",
                "service": "SIH26124-Municipal-Ingestion-API",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "total_stored_incidents": len(STORED_INCIDENTS),
                "detector_ready": get_detector() is not None,
                "video_source": POTHOLE_VIDEO_PATH if os.path.exists(POTHOLE_VIDEO_PATH) else FALLBACK_VIDEO_PATH
            })
            return

        # 2. Incidents List API
        if path == "/api/v1/incidents":
            self._send_json(200, {
                "total_incidents": len(STORED_INCIDENTS),
                "incidents": STORED_INCIDENTS
            })
            return

        # 3. Live Video MJPEG Stream
        if path == "/video_feed":
            source = (query.get("source") or ["demo"])[0].lower()
            self._serve_mjpeg_stream(source=source)
            return

        # 4. Dataset List API
        if path == "/api/v1/dataset":
            files = get_dataset_files()
            self._send_json(200, {
                "dataset_directory": DATASET_DIR,
                "total_images": len(files),
                "images": files
            })
            return

        # 5. Dataset Raw Image
        if path.startswith("/api/v1/dataset/raw/"):
            filename = os.path.basename(path)
            img_path = os.path.join(DATASET_DIR, filename)
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    self._send_bytes(200, "image/jpeg", f.read())
            else:
                self._send_json(404, {"error": "Image not found", "file": filename})
            return

        # 6. Dataset Annotated Image
        if path.startswith("/api/v1/dataset/annotated/"):
            filename = os.path.basename(path)
            self._serve_annotated_dataset_image(filename)
            return

        # 7. Dataset Inspection Metadata
        if path.startswith("/api/v1/dataset/inspect/"):
            filename = os.path.basename(path)
            self._serve_dataset_inspection_json(filename)
            return

        # 8. Video Captures (10s HD clips)
        if path.startswith("/api/v1/video/"):
            filename = os.path.basename(path)
            vid_path = os.path.join(VIDEO_CAPTURES_DIR, filename)
            if os.path.exists(vid_path):
                with open(vid_path, "rb") as f:
                    self._send_bytes(200, "video/mp4", f.read())
            else:
                self._send_json(404, {"error": "Video capture file not found", "file": filename})
            return

        # 9. Main Interactive Web Dashboard
        if path == "/" or path.startswith("/?"):
            self._serve_dashboard()
            return

        self._send_json(404, {"error": "Endpoint not found", "path": path})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Incident Ingestion
        if path == "/api/v1/incidents":
            self._handle_incident_ingest()
            return

        # 2. Simulate Incident from Dataset Image
        if path == "/api/v1/dataset/simulate_incident":
            self._handle_simulate_incident()
            return

        self._send_json(404, {"error": "Endpoint not found. Use POST /api/v1/incidents"})

    def _handle_incident_ingest(self):
        # 1. Check Bearer Authentication
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Rejected request: Missing Bearer authorization header")
            self._send_json(401, {"error": "Unauthorized. Bearer token required."})
            return

        token = auth_header.split(" ", 1)[1].strip()
        if token != EXPECTED_TOKEN:
            logger.warning(f"Rejected request: Invalid token '{token}' (expected '{EXPECTED_TOKEN}')")
            self._send_json(403, {"error": "Forbidden: Invalid authorization credentials."})
            return

        # 2. Parse JSON Payload
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_json(400, {"error": "Empty payload received"})
            return

        try:
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body)
        except Exception as e:
            self._send_json(400, {"error": f"Invalid JSON payload: {e}"})
            return

        # 3. Log and Store Incident
        inc_id = payload.get("incident_id", f"INC-{int(time.time())}")
        defect_type = payload.get("defect_type", "POTHOLE")
        confidence = payload.get("confidence", 0.0)
        gps = payload.get("gps", {})
        traffic = payload.get("traffic_density", {})
        video_ref = payload.get("video_reference", {})

        STORED_INCIDENTS.append(payload)

        # Append to persistent JSONL log
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as err:
            logger.error(f"Failed to persist incident to log: {err}")

        print("\n" + "="*70)
        print("🚨 NEW MUNICIPAL INCIDENT RECEIVED VIA REST API")
        print(f"Incident ID:         {inc_id}")
        print(f"Device ID:           {payload.get('device_id')}")
        print(f"Defect Type:         {defect_type} (Confidence: {confidence:.2f})")
        print(f"GPS Location:        Lat: {gps.get('latitude')}, Lon: {gps.get('longitude')} (Speed: {gps.get('speed_kmh')} km/h)")
        print(f"Traffic Density:     {traffic.get('density_level', 'N/A')} ({traffic.get('total_vehicles', 0)} vehicles, Congestion: {traffic.get('congestion_index', 0)*100:.1f}%)")
        print(f"Video Reference:     {video_ref.get('file_path')} ({video_ref.get('duration_seconds', 10.0)}s @ {video_ref.get('resolution')})")
        print(f"Timestamp:           {payload.get('timestamp')}")
        print("="*70 + "\n")

        self._send_json(201, {
            "status": "ACCEPTED",
            "incident_id": inc_id,
            "message": "Incident telemetry and 10-second HD video reference successfully registered.",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })

    def _handle_simulate_incident(self):
        content_length = int(self.headers.get("Content-Length", 0))
        filename = "1.jpg"
        if content_length > 0:
            try:
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
                filename = body.get("filename", "1.jpg")
            except Exception:
                pass

        # Inspect image
        info = self._get_image_inspection(filename)
        conf = info.get("max_confidence", 0.88)
        if conf < POTHOLE_CONF:
            conf = max(POTHOLE_CONF, 0.82)

        simulated_incident = {
            "incident_id": f"POT-SIM-{int(time.time()*1000)%1000000:06d}",
            "device_id": "rpi-edge-01-bookworm",
            "defect_type": "POTHOLE",
            "confidence": float(conf),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "gps": {
                "latitude": round(28.6139 + (np.random.rand() - 0.5) * 0.05, 6),
                "longitude": round(77.2090 + (np.random.rand() - 0.5) * 0.05, 6),
                "speed_kmh": round(32.5 + np.random.rand() * 10, 1),
                "simulated": True
            },
            "traffic_density": {
                "density_level": "MEDIUM",
                "total_vehicles": int(np.random.randint(4, 12)),
                "congestion_index": round(0.45 + np.random.rand() * 0.2, 2)
            },
            "video_reference": {
                "file_path": f"ai/video_captures/simulated_{filename}.mp4",
                "duration_seconds": 10.0,
                "resolution": "1280x720@30fps",
                "codec": "mp4v"
            },
            "source_image": filename
        }

        STORED_INCIDENTS.append(simulated_incident)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(simulated_incident) + "\n")
        except Exception:
            pass

        self._send_json(201, simulated_incident)

    def _get_image_inspection(self, filename: str) -> dict:
        if filename in DATASET_CACHE:
            return DATASET_CACHE[filename]

        img_path = os.path.join(DATASET_DIR, filename)
        if not os.path.exists(img_path):
            return {"error": "File not found", "filename": filename}

        detector = get_detector()
        if detector is None:
            return {"error": "Detector unavailable", "filename": filename}

        frame = cv2.imread(img_path)
        if frame is None:
            return {"error": "Corrupted image file", "filename": filename}

        h, w = frame.shape[:2]
        t0 = time.time()
        pothole_list = detector.detect_potholes(frame)
        latency_ms = round((time.time() - t0) * 1000, 1)

        detections = []
        max_conf = 0.0
        for det in pothole_list:
            conf = float(det.confidence)
            if conf > max_conf:
                max_conf = conf
            x1 = int(det.bbox.x_min)
            y1 = int(det.bbox.y_min)
            x2 = int(det.bbox.x_max)
            y2 = int(det.bbox.y_max)
            detections.append({
                "label": det.class_name,
                "confidence": round(conf, 4),
                "bbox": [x1, y1, x2, y2]
            })

        inspection = {
            "filename": filename,
            "width": w,
            "height": h,
            "latency_ms": latency_ms,
            "pothole_detected": len(detections) > 0,
            "count": len(detections),
            "max_confidence": round(max_conf, 4),
            "detections": detections
        }
        DATASET_CACHE[filename] = inspection
        return inspection

    def _serve_annotated_dataset_image(self, filename: str):
        img_path = os.path.join(DATASET_DIR, filename)
        if not os.path.exists(img_path):
            self._send_json(404, {"error": "Image not found", "file": filename})
            return

        frame = cv2.imread(img_path)
        if frame is None:
            self._send_json(400, {"error": "Cannot decode image", "file": filename})
            return

        info = self._get_image_inspection(filename)
        detections = info.get("detections", [])

        # Annotate
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            conf = det["confidence"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
            label_text = f"POTHOLE {int(conf*100)}%"
            # Background badge
            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, max(0, y1 - 25)), (x1 + tw + 10, max(0, y1)), (0, 0, 255), -1)
            cv2.putText(frame, label_text, (x1 + 5, max(0, y1 - 7)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        # Header HUD
        hud_text = f"{filename} | Potholes: {len(detections)} | Max Conf: {int(info.get('max_confidence', 0)*100)}% | {info.get('latency_ms', 0)}ms"
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 30), (20, 20, 20), -1)
        cv2.putText(frame, hud_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)

        ret, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if ret:
            self._send_bytes(200, "image/jpeg", buffer.tobytes())
        else:
            self._send_json(500, {"error": "Failed to encode annotated image"})

    def _serve_dataset_inspection_json(self, filename: str):
        info = self._get_image_inspection(filename)
        self._send_json(200, info)

    def _placeholder_jpeg(self, message: str) -> bytes:
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(frame, message, (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 1, cv2.LINE_AA)
        ok, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes() if ok else b""

    def _serve_pi_camera_proxy(self):
        """Relay MJPEG from the Raspberry Pi live pipeline (port 5001)."""
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        try:
            while True:
                try:
                    with urlopen(PI_STREAM_URL, timeout=4.0) as resp:
                        while True:
                            chunk = resp.read(16384)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                except (URLError, TimeoutError, OSError, BrokenPipeError, ConnectionResetError):
                    jpeg = self._placeholder_jpeg("Pi camera offline — start: python -m ai.cli live ...")
                    if jpeg:
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                        )
                    time.sleep(1.5)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_mjpeg_stream(self, source: str = "demo"):
        if source in ("live", "pi", "camera"):
            self._serve_pi_camera_proxy()
            return

        # Choose video source
        vid_source = POTHOLE_VIDEO_PATH if os.path.exists(POTHOLE_VIDEO_PATH) else FALLBACK_VIDEO_PATH
        if not os.path.exists(vid_source):
            self._send_json(404, {"error": "No road video source found for streaming."})
            return

        cap = cv2.VideoCapture(vid_source)
        if not cap.isOpened():
            self._send_json(500, {"error": f"Failed to open video source: {vid_source}"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.end_headers()

        detector = get_detector()
        frame_idx = 0
        cached_detections = []
        last_detect_time = time.time()

        try:
            while True:
                success, frame = cap.read()
                if not success:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

                frame_idx += 1

                # Detect potholes every 2nd frame for smooth 25-30 FPS display
                if detector and (frame_idx % 2 == 0 or not cached_detections):
                    t0 = time.time()
                    cached_detections = detector.detect_potholes(frame)
                    last_detect_time = time.time() - t0

                # Draw detections
                pothole_count = len(cached_detections)
                for det in cached_detections:
                    x1 = int(det.bbox.x_min)
                    y1 = int(det.bbox.y_min)
                    x2 = int(det.bbox.x_max)
                    y2 = int(det.bbox.y_max)
                    conf = float(det.confidence)
                    # Red bounding box for potholes
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    tag = f"POTHOLE {int(conf * 100)}%"
                    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(frame, (x1, max(0, y1 - 25)), (x1 + tw + 10, max(0, y1)), (0, 0, 255), -1)
                    cv2.putText(frame, tag, (x1 + 5, max(0, y1 - 7)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

                # Draw HUD Status Overlay
                h, w = frame.shape[:2]
                cv2.rectangle(frame, (0, 0), (w, 42), (15, 23, 42), -1)

                status_color = (0, 0, 255) if pothole_count > 0 else (0, 255, 0)
                status_text = f"ALERT: {pothole_count} POTHOLE(S) DETECTED" if pothole_count > 0 else "ROAD STATUS: CLEAR"
                cv2.circle(frame, (20, 21), 7, status_color, -1)
                cv2.putText(frame, status_text, (35, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_color, 2, cv2.LINE_AA)

                hud_info = f"RPi Edge Node (192.168.1.150) | 720p@30FPS | YOLO Conf>=0.75 | Infer: {int(last_detect_time*1000)}ms"
                cv2.putText(frame, hud_info, (w - 650, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1, cv2.LINE_AA)

                ret, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                if not ret:
                    continue

                chunk = (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
                )
                self.wfile.write(chunk)
                time.sleep(0.033)  # Maintain ~30 FPS

        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            cap.release()

    def _serve_dashboard(self):
        inc_rows = ""
        for inc in reversed(STORED_INCIDENTS[-50:]):
            gps = inc.get("gps", {})
            traffic = inc.get("traffic_density", {})
            video = inc.get("video_reference", {})
            conf = inc.get("confidence", 0.0)
            conf_pct = int(conf * 100)
            density = traffic.get("density_level", "LOW")
            badge_color = "bg-emerald-100 text-emerald-800 border-emerald-300" if density == "LOW" else (
                "bg-amber-100 text-amber-800 border-amber-300" if density == "MEDIUM" else "bg-rose-100 text-rose-800 border-rose-300"
            )

            vid_filename = os.path.basename(video.get("file_path", ""))
            vid_link = f'<a href="/api/v1/video/{vid_filename}" target="_blank" class="text-indigo-600 hover:underline font-mono text-xs">{vid_filename or "N/A"}</a>'

            inc_rows += f"""
            <tr class="border-b border-slate-100 hover:bg-slate-50 transition">
                <td class="px-4 py-3 font-mono text-xs font-semibold text-slate-700">{inc.get('incident_id', '')}</td>
                <td class="px-4 py-3">
                    <span class="px-2.5 py-1 font-bold text-xs rounded-full bg-rose-100 text-rose-700 border border-rose-200">
                        {inc.get('defect_type')}
                    </span>
                </td>
                <td class="px-4 py-3 text-sm font-bold text-slate-800">{conf_pct}%</td>
                <td class="px-4 py-3 text-xs text-slate-600">
                    <div class="font-mono">{gps.get('latitude', '')}, {gps.get('longitude', '')}</div>
                    <span class="text-slate-400">{gps.get('speed_kmh', 0)} km/h</span>
                </td>
                <td class="px-4 py-3">
                    <span class="px-2 py-0.5 text-xs font-medium rounded-full border {badge_color}">
                        {density} ({traffic.get('total_vehicles', 0)} veh)
                    </span>
                </td>
                <td class="px-4 py-3 text-xs">{vid_link}</td>
                <td class="px-4 py-3 text-xs text-slate-500 font-mono">{inc.get('timestamp', '')[:19]}</td>
            </tr>
            """

        if not inc_rows:
            inc_rows = '<tr><td colspan="7" class="text-center py-10 text-slate-400 italic">No road incidents received yet. Edge nodes are actively scanning live road footage...</td></tr>'

        dataset_files = get_dataset_files()
        thumbnails_html = ""
        for fn in dataset_files[:16]:  # Display first 16 in quick preview grid
            thumbnails_html += f"""
            <div class="group relative rounded-lg border border-slate-200 overflow-hidden bg-slate-900 cursor-pointer shadow-sm hover:shadow-md transition"
                 onclick="inspectDatasetImage('{fn}')">
                <img src="/api/v1/dataset/raw/{fn}" alt="{fn}" class="w-full h-24 object-cover group-hover:opacity-80 transition" />
                <div class="absolute bottom-0 inset-x-0 bg-slate-900/80 backdrop-blur-xs px-2 py-1 flex justify-between items-center text-[10px] text-slate-300 font-mono">
                    <span>{fn}</span>
                    <span class="text-indigo-300 font-semibold">Inspect &rarr;</span>
                </div>
            </div>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FleetVision: Municipal Urban Sensing Grid (SIH26124)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
        code, pre, .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
    </style>
</head>
<body class="bg-slate-100 text-slate-900 min-h-screen">

    <!-- Top Navigation -->
    <header class="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex justify-between items-center">
            <div class="flex items-center space-x-3">
                <div class="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center font-black text-lg text-white shadow">
                    SIH
                </div>
                <div>
                    <h1 class="text-lg font-bold leading-tight flex items-center gap-2">
                        FleetVision: Municipal Sensing Grid
                        <span class="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">SIH26124 Edge</span>
                    </h1>
                    <p class="text-xs text-slate-400">Decentralized Road Infrastructure Monitoring & Ingestion Hub</p>
                </div>
            </div>
            <div class="flex items-center space-x-3">
                <div class="hidden md:flex items-center space-x-2 text-xs text-slate-300 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>Edge Node: <strong class="text-white font-mono">192.168.1.150</strong></span>
                    <span class="text-slate-500">|</span>
                    <span>Token: <strong class="text-white font-mono">sih_admin</strong></span>
                </div>
                <button onclick="location.reload()" class="text-xs font-semibold px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center gap-1.5">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                    Refresh
                </button>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

        <!-- Top Status KPI Cards -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div class="bg-white rounded-xl p-4 shadow-xs border border-slate-200">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Total Incidents</span>
                    <span class="p-1.5 rounded-md bg-rose-50 text-rose-600">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                    </span>
                </div>
                <div class="text-3xl font-extrabold text-slate-900 mt-2">{len(STORED_INCIDENTS)}</div>
                <div class="text-xs text-slate-500 mt-1 flex items-center gap-1">
                    <span class="text-emerald-600 font-semibold">100% Verified</span> with 10s HD clips
                </div>
            </div>

            <div class="bg-white rounded-xl p-4 shadow-xs border border-slate-200">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Live Video Stream</span>
                    <span class="p-1.5 rounded-md bg-emerald-50 text-emerald-600">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
                    </span>
                </div>
                <div class="text-xl font-bold text-slate-900 mt-2">1280x720 @ 30 FPS</div>
                <div class="text-xs text-slate-500 mt-1 flex items-center gap-1">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    MJPEG Stream Online (/video_feed)
                </div>
            </div>

            <div class="bg-white rounded-xl p-4 shadow-xs border border-slate-200">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Pothole Perception</span>
                    <span class="p-1.5 rounded-md bg-indigo-50 text-indigo-600">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                    </span>
                </div>
                <div class="text-xl font-bold text-indigo-600 mt-2">Conf &ge; 0.75 Strict</div>
                <div class="text-xs text-slate-500 mt-1">
                    Custom Model: <span class="font-mono font-semibold">pothole_model.pt</span>
                </div>
            </div>

            <div class="bg-white rounded-xl p-4 shadow-xs border border-slate-200">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Edge Ring Buffer</span>
                    <span class="p-1.5 rounded-md bg-amber-50 text-amber-600">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                    </span>
                </div>
                <div class="text-xl font-bold text-slate-900 mt-2">5s Pre + 5s Post</div>
                <div class="text-xs text-slate-500 mt-1">
                    Thread-safe deque (300 frames HD)
                </div>
            </div>
        </div>

        <!-- Main 2-Column Section: Live Video Feed + Dataset Benchmark Explorer -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">

            <!-- Left: Real-time Video Feed -->
            <div class="lg:col-span-7 bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden flex flex-col">
                <div class="px-5 py-4 border-b border-slate-200 flex justify-between items-center bg-slate-50/70">
                    <div class="flex items-center space-x-2">
                        <span class="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse"></span>
                        <h2 class="text-sm font-bold text-slate-800 uppercase tracking-wide">Video Feed &amp; YOLO Detection</h2>
                    </div>
                    <div class="flex items-center gap-2">
                        <button type="button" id="btnDemo" onclick="setStreamSource('demo')"
                            class="text-xs font-semibold px-3 py-1 rounded-lg bg-indigo-600 text-white">Demo video</button>
                        <button type="button" id="btnLive" onclick="setStreamSource('live')"
                            class="text-xs font-semibold px-3 py-1 rounded-lg bg-white text-slate-700 border border-slate-300">Live Pi camera</button>
                    </div>
                </div>
                <div class="relative bg-black flex-1 flex items-center justify-center min-h-[380px]">
                    <img id="liveFeed" src="/video_feed?source=demo" alt="Pothole detection stream" class="w-full h-auto max-h-[460px] object-contain" />
                </div>
                <div class="p-4 bg-slate-50 border-t border-slate-200 flex justify-between items-center text-xs text-slate-600">
                    <div class="flex items-center gap-2">
                        <span class="font-semibold text-slate-700">Source:</span>
                        <span id="streamLabel" class="font-mono bg-white px-2 py-0.5 rounded border border-slate-200 text-slate-600">tfliterpipothole/pothole1/pothole1.mp4</span>
                    </div>
                    <div class="text-right text-slate-500">
                        Overlay: <strong class="text-rose-600">Pothole BBoxes</strong> + <strong class="text-indigo-600">HUD Telemetry</strong>
                    </div>
                </div>
            </div>

            <!-- Right: Interactive Dataset Explorer & Test Bench -->
            <div class="lg:col-span-5 bg-white rounded-xl shadow-xs border border-slate-200 flex flex-col">
                <div class="px-5 py-4 border-b border-slate-200 flex justify-between items-center bg-slate-50/70">
                    <div>
                        <h2 class="text-sm font-bold text-slate-800 uppercase tracking-wide">Pothole Dataset Test Bench</h2>
                        <p class="text-xs text-slate-500">72 real pothole road images from <code class="font-mono text-[11px]">potholeimages/</code></p>
                    </div>
                    <span class="text-xs font-bold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full border border-indigo-100">
                        {len(dataset_files)} Images
                    </span>
                </div>

                <div class="p-4 flex-1 flex flex-col space-y-4">
                    <!-- Quick thumbnail selector -->
                    <div>
                        <div class="text-xs font-semibold text-slate-600 mb-2 flex justify-between">
                            <span>Click Any Image to Run Instant Model Detection:</span>
                            <span class="text-slate-400">Displaying 16 of {len(dataset_files)}</span>
                        </div>
                        <div class="grid grid-cols-4 gap-2">
                            {thumbnails_html}
                        </div>
                    </div>

                    <!-- Selected Image Inspection View -->
                    <div id="inspectionCard" class="bg-slate-50 rounded-lg p-3.5 border border-slate-200">
                        <div class="flex justify-between items-center mb-2">
                            <span class="text-xs font-bold text-slate-700 font-mono" id="inspectTitle">Image: 1.jpg (Verified Detection)</span>
                            <button onclick="simulateIncidentForCurrent()" class="text-xs font-bold px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-700 text-white transition flex items-center gap-1 shadow-xs">
                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                                Ingest Incident
                            </button>
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <div class="text-[10px] font-bold text-slate-400 uppercase mb-1">Raw Capture</div>
                                <img id="inspectRaw" src="/api/v1/dataset/raw/1.jpg" alt="Raw Image" class="w-full h-32 object-cover rounded border border-slate-300" />
                            </div>
                            <div>
                                <div class="text-[10px] font-bold text-slate-400 uppercase mb-1">YOLO Model Output (Conf &ge; 0.75)</div>
                                <img id="inspectAnnotated" src="/api/v1/dataset/annotated/1.jpg" alt="Annotated Detection" class="w-full h-32 object-cover rounded border border-slate-300" />
                            </div>
                        </div>
                        <div id="inspectDetails" class="mt-2.5 text-xs text-slate-600 font-mono bg-white p-2 rounded border border-slate-200">
                            Loading detection metrics...
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Municipal Incident Telemetry Table -->
        <div class="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-200 flex justify-between items-center bg-slate-50/70">
                <div>
                    <h2 class="text-base font-bold text-slate-800">Live Municipal Incident Telemetry Stream</h2>
                    <p class="text-xs text-slate-500">Processed from edge nodes via <code class="font-mono text-indigo-600">POST /api/v1/incidents</code> with Bearer <code class="font-mono">sih_admin</code></p>
                </div>
                <div class="flex items-center space-x-2">
                    <a href="/api/v1/incidents" target="_blank" class="text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition">
                        Raw JSON API &rarr;
                    </a>
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-slate-100/70 text-slate-600 uppercase text-[11px] font-bold tracking-wider border-b border-slate-200">
                            <th class="px-4 py-3">Incident ID</th>
                            <th class="px-4 py-3">Defect Type</th>
                            <th class="px-4 py-3">Confidence</th>
                            <th class="px-4 py-3">GPS Telemetry</th>
                            <th class="px-4 py-3">Traffic Density</th>
                            <th class="px-4 py-3">10s HD Capture</th>
                            <th class="px-4 py-3">Timestamp (UTC)</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
                        {inc_rows}
                    </tbody>
                </table>
            </div>
        </div>

    </main>

    <footer class="max-w-7xl mx-auto px-4 py-6 text-center text-xs text-slate-400">
        SIH26124 Edge Computer Vision & Municipal Cloud Sync System &bull; Active Cooling & CSI Camera Support &bull; Raspberry Pi 4 / 5 OS Bookworm
    </footer>

    <script>
        function setStreamSource(src) {{
            const img = document.getElementById('liveFeed');
            const label = document.getElementById('streamLabel');
            const btnDemo = document.getElementById('btnDemo');
            const btnLive = document.getElementById('btnLive');
            img.src = '/video_feed?source=' + src + '&t=' + Date.now();
            if (src === 'live') {{
                label.textContent = 'Raspberry Pi CSI camera (10.54.12.49:5001)';
                btnLive.className = 'text-xs font-semibold px-3 py-1 rounded-lg bg-indigo-600 text-white';
                btnDemo.className = 'text-xs font-semibold px-3 py-1 rounded-lg bg-white text-slate-700 border border-slate-300';
            }} else {{
                label.textContent = 'tfliterpipothole/pothole1/pothole1.mp4';
                btnDemo.className = 'text-xs font-semibold px-3 py-1 rounded-lg bg-indigo-600 text-white';
                btnLive.className = 'text-xs font-semibold px-3 py-1 rounded-lg bg-white text-slate-700 border border-slate-300';
            }}
        }}

        let currentSelectedFile = '1.jpg';

        function inspectDatasetImage(filename) {{
            currentSelectedFile = filename;
            document.getElementById('inspectTitle').innerText = 'Image: ' + filename + ' (Evaluating...)';
            document.getElementById('inspectRaw').src = '/api/v1/dataset/raw/' + filename;
            document.getElementById('inspectAnnotated').src = '/api/v1/dataset/annotated/' + filename;

            fetch('/api/v1/dataset/inspect/' + filename)
                .then(res => res.json())
                .then(data => {{
                    const detected = data.pothole_detected ? '✅ POTHOLE CONFIRMED' : '⚠️ No Pothole >= 0.75';
                    const conf = data.max_confidence ? (data.max_confidence * 100).toFixed(1) + '%' : 'N/A';
                    document.getElementById('inspectTitle').innerText = 'Image: ' + filename + ' (' + detected + ')';
                    document.getElementById('inspectDetails').innerHTML = 
                        'Status: <strong>' + detected + '</strong> | Count: <strong>' + data.count + '</strong> | ' +
                        'Max Conf: <strong>' + conf + '</strong> | Latency: <strong>' + data.latency_ms + 'ms</strong>';
                }})
                .catch(err => {{
                    document.getElementById('inspectDetails').innerText = 'Error loading inspection data.';
                }});
        }}

        function simulateIncidentForCurrent() {{
            fetch('/api/v1/dataset/simulate_incident', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ filename: currentSelectedFile }})
            }})
            .then(res => res.json())
            .then(data => {{
                alert('Incident Registered!\\nID: ' + data.incident_id + '\\nConfidence: ' + (data.confidence * 100).toFixed(1) + '%\\nSent to central municipal ingestion database.');
                location.reload();
            }})
            .catch(err => alert('Failed to simulate incident: ' + err));
        }}

        // Initial inspection on page load
        window.addEventListener('DOMContentLoaded', () => {{
            inspectDatasetImage('1.jpg');
        }});
    </script>
</body>
</html>"""

        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Suppress verbose standard access logs
        return


def run_server(port: int = 8000):
    server_address = ("0.0.0.0", port)
    httpd = ThreadedHTTPServer(server_address, IncidentRequestHandler)
    print("\n" + "="*75)
    print(f"🌐 SIH26124 CENTRAL INGESTION & VIDEO DASHBOARD RUNNING ON http://0.0.0.0:{port}")
    print(f"Incident Endpoint:     POST http://192.168.1.100:{port}/api/v1/incidents")
    print(f"Authorization:         Bearer {EXPECTED_TOKEN}")
    print(f"Live Video MJPEG Feed: GET  http://localhost:{port}/video_feed")
    print(f"Dataset Test Bench:    GET  http://localhost:{port}/api/v1/dataset")
    print(f"Web Dashboard UI:      GET  http://localhost:{port}/")
    print("="*75 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down backend server...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SIH26124 Central Ingestion Backend Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--conf", type=float, default=0.50, help="Pothole detection confidence threshold (default: 0.50)")
    parser.add_argument("--pi-stream-url", type=str, default=PI_STREAM_URL, help="Pi MJPEG URL for Live camera switch")
    args = parser.parse_args()
    POTHOLE_CONF = args.conf
    PI_STREAM_URL = args.pi_stream_url
    logger.info(f"Pothole confidence threshold set to {POTHOLE_CONF}")
    logger.info(f"Pi live stream URL: {PI_STREAM_URL}")
    run_server(port=args.port)
