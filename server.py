"""
Flask Development Server for Municipal AI Monitoring & MJPEG Video Feed.

Provides:
- GET /video_feed: Real-time MJPEG stream of pothole road footage with YOLO detections.
- GET /api/status: System status and edge node health.
- GET /api/incidents: List of recent detected incidents.

Usage:
  python server.py
"""

import datetime
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import numpy as np
from flask import Flask, jsonify, Response
from flask_cors import CORS

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

app = Flask(__name__)
CORS(app)

POTHOLE_VIDEO_PATH = os.path.join(PROJECT_ROOT, "tfliterpipothole", "pothole1", "pothole1.mp4")
FALLBACK_VIDEO_PATH = os.path.join(PROJECT_ROOT, "ai", "samples", "real_pothole_720p.mp4")
MODEL_PATH = os.path.join(PROJECT_ROOT, "ai", "models", "pothole_model.pt")
POTHOLE_CONF = float(os.environ.get("POTHOLE_CONF", "0.50"))

# Lazy detector loader
_DETECTOR = None

def get_detector():
    global _DETECTOR
    if _DETECTOR is None:
        try:
            from ai.detector import PotholeDetector
            if os.path.exists(MODEL_PATH):
                _DETECTOR = PotholeDetector(model_path=MODEL_PATH, confidence_threshold=POTHOLE_CONF, device="cpu")
        except Exception:
            _DETECTOR = None
    return _DETECTOR


@app.route('/api/status', methods=['GET'])
def get_status():
    status_data = {
        "status": "ONLINE",
        "service": "SIH26124-Edge-Stream-Service",
        "node_ip": "192.168.1.150",
        "resolution": "1280x720@30FPS",
        "model": "pothole_model.pt",
        "confidence_threshold": POTHOLE_CONF,
        "active_stream": os.path.exists(POTHOLE_VIDEO_PATH) or os.path.exists(FALLBACK_VIDEO_PATH),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    if os.path.exists("dashboard_data.json"):
        try:
            with open("dashboard_data.json", "r") as f:
                status_data.update(json.load(f))
        except Exception:
            pass
    return jsonify(status_data)


@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    incidents = []
    # Check received_incidents.jsonl in scripts
    jsonl_path = os.path.join(PROJECT_ROOT, "scripts", "received_incidents.jsonl")
    if os.path.exists(jsonl_path):
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        incidents.append(json.loads(line.strip()))
        except Exception:
            pass
    elif os.path.exists("incidents.json"):
        try:
            with open("incidents.json", "r") as f:
                incidents = json.load(f)
        except Exception:
            pass
    return jsonify(incidents)


def generate_video_frames():
    vid_source = POTHOLE_VIDEO_PATH if os.path.exists(POTHOLE_VIDEO_PATH) else FALLBACK_VIDEO_PATH
    if not os.path.exists(vid_source):
        # Generate dummy frame if no video exists
        while True:
            blank = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(blank, "NO ROAD FOOTAGE VIDEO FOUND", (400, 360),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', blank)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.1)

    cap = cv2.VideoCapture(vid_source)
    detector = get_detector()
    frame_idx = 0
    cached_detections = []

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame_idx += 1

            # Detect potholes every 2nd frame
            if detector and (frame_idx % 2 == 0 or not cached_detections):
                cached_detections = detector.detect_potholes(frame)

            pothole_count = len(cached_detections)
            for det in cached_detections:
                x1 = int(det.bbox.x_min)
                y1 = int(det.bbox.y_min)
                x2 = int(det.bbox.x_max)
                y2 = int(det.bbox.y_max)
                conf = float(det.confidence)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                tag = f"POTHOLE {int(conf * 100)}%"
                (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(frame, (x1, max(0, y1 - 25)), (x1 + tw + 10, max(0, y1)), (0, 0, 255), -1)
                cv2.putText(frame, tag, (x1 + 5, max(0, y1 - 7)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

            # HUD
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (0, 0), (w, 40), (15, 23, 42), -1)
            status_color = (0, 0, 255) if pothole_count > 0 else (0, 255, 0)
            status_text = f"ALERT: {pothole_count} POTHOLE(S) DETECTED" if pothole_count > 0 else "ROAD STATUS: CLEAR"
            cv2.putText(frame, status_text, (20, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2, cv2.LINE_AA)
            cv2.putText(frame, f"SIH26124 Edge Stream | 720p@30FPS | YOLOv8 Conf>={POTHOLE_CONF:.2f}",
                        (w - 520, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            if not ret:
                continue

            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.033)
    finally:
        cap.release()


@app.route('/video_feed')
def video_feed():
    return Response(generate_video_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/')
def index():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SIH26124 Edge Video Feed</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }}
    header {{ padding: 1rem 1.5rem; background: #1e293b; border-bottom: 1px solid #334155; }}
    main {{ padding: 1.5rem; max-width: 1200px; margin: 0 auto; }}
    img {{ width: 100%; max-width: 1280px; border: 2px solid #334155; border-radius: 8px; background: #000; }}
    a {{ color: #93c5fd; }}
    .links {{ margin-top: 1rem; display: flex; gap: 1rem; flex-wrap: wrap; }}
    .badge {{ background: #334155; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <header>
    <h1>SIH26124 — Live Pothole Detection Stream</h1>
    <p>Confidence threshold: <span class="badge">&ge; {POTHOLE_CONF:.2f}</span></p>
  </header>
  <main>
    <img src="/video_feed" alt="Live pothole detection MJPEG stream">
    <div class="links">
      <a href="/video_feed">Raw MJPEG feed</a>
      <a href="/api/status">API status (JSON)</a>
      <a href="/api/incidents">Incidents (JSON)</a>
    </div>
    <p style="margin-top:1rem;color:#94a3b8;font-size:0.9rem;">
      Full dashboard with dataset explorer: run
      <code>python scripts/mock_backend.py --port 8000 --conf 0.50</code>
      then open <a href="http://127.0.0.1:8000">http://127.0.0.1:8000</a>
    </p>
  </main>
</body>
</html>"""


@app.route('/favicon.ico')
def favicon():
    return Response(status=204)


if __name__ == '__main__':
    print("Starting SIH Flask Edge Video Feed Server on http://0.0.0.0:5000 ...")
    app.run(host='0.0.0.0', port=5000, threaded=True)