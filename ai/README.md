# SIH26124 AI Perception Layer

This directory contains the complete **Phase 1 AI Perception Layer** for **SIH26124** (Public Transport Mobile Road Sensing Platform). It implements a modular architecture separating **Pothole Detection**, **Traffic Density Estimation**, **Zebra Crossing Analysis**, and the **Unified Real-Time Road Intelligence Video Pipeline**.

---

## 🏗️ Architecture & Component Layout

```
ai/
├── common/                     # Reusable data models & JSON serializers
│   ├── __init__.py
│   └── models.py               # BoundingBox, AIObservation, PipelineResult
│
├── pothole/                    # [IMPLEMENTED] Pothole Detection Subsystem
│   ├── __init__.py
│   ├── detector.py             # PotholeDetector (YOLO wrapper with validation)
│   └── downloader.py           # Downloader for Harisanth/Pothole-Finetuned-YOLOv8
│
├── zebra_crossing/             # [PROTOTYPE / REQUIRES TRAINED MODEL] Zebra Crossing Subsystem
│   ├── __init__.py
│   └── detector.py             # ZebraCrossingDetector interface & prototype stub
│
├── traffic/                    # [IMPLEMENTED] Traffic Density Estimation Subsystem
│   ├── __init__.py
│   └── density.py              # TrafficDensityEstimator (Vehicle detection & ROI density)
│
├── traffic_signal/             # [IMPLEMENTED DETECTION / PROTOTYPE STATE] Traffic Signal Intelligence
│   ├── __init__.py
│   └── detector.py             # TrafficSignalDetector (Signal detection, state recognition & health)
│
├── tests/                      # Automated Test Suite
│   ├── test_common.py
│   ├── test_pothole.py
│   ├── test_zebra_crossing.py
│   ├── test_traffic.py
│   ├── test_traffic_signal.py
│   ├── test_tracker.py
│   └── test_road_intelligence.py
│
├── road_intelligence.py        # [IMPLEMENTED] Unified Video Pipeline Engine
├── pipeline.py                 # AIPipeline frame orchestrator
├── cli.py                      # Master CLI runner
├── requirements.txt
└── README.md
```

---

## 📌 Feature Implementation Matrix

| Module | Feature | Implementation Status | Model / Methodology Used |
| :--- | :--- | :--- | :--- |
| `ai/detector.py` | **Edge Detector & Ring Buffer** | `[IMPLEMENTED]` | PyTorch Ultralytics YOLO with strict 0.75 threshold, 1280x720 @ 30 FPS, hardware AEC/AWB, collections.deque 5s pre + 5s post capture (10s HD .mp4), async video writer worker. |
| `ai/aggregator.py` | **Telemetry Aggregator & SQLite Queue** | `[IMPLEMENTED]` | REST transmission to `http://192.168.1.100:8000/api/v1/incidents` (Bearer `sih_admin`), resilient SQLite offline queue, sample/hardware GPS. |
| `ai/cli.py` | **Edge CLI** | `[IMPLEMENTED]` | Modular CLI supporting `live`, `video`, `test-camera`, `sync`, `status`, and `traffic`. |
| `ai/pothole/` | **Pothole Detection** | `[IMPLEMENTED]` | Authentic fine-tuned YOLO model (`ai/models/pothole_model.pt`). |
| `ai/traffic/` | **Traffic Density Estimation** | `[IMPLEMENTED]` | Vehicle counting (`car`, `bus`, `truck`, `motorcycle`) using `yolov8n.pt`. Volumetric density classification into `LOW`, `MEDIUM`, `HIGH`. |
| `ai/record_road_footage.py` | **CSI Camera Recorder** | `[IMPLEMENTED]` | Live 1280x720 30FPS footage capture tool for Raspberry Pi CSI camera module. |
| `scripts/infra_monitor.service` | **Systemd Service** | `[IMPLEMENTED]` | Auto-boot daemon with crash recovery (`Restart=always`, `RestartSec=5s`). |
| `scripts/cleanup_storage.sh` | **Storage Purge Routine** | `[IMPLEMENTED]` | 24-hour cleanup purging synced `.mp4` captures older than 7 days. |

---

## 🚀 Setup & Command Execution

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Download Pothole Model Weights
```bash
python -m ai.pothole.downloader
```

### 3. Run Automated Unit Test Suite (26 Tests)
```bash
python -m unittest discover -s ai/tests -p "test_*.py"
```

### 4. Run Unified Video Pipeline CLI
```bash
python -m ai.cli --source sample_video.mp4 --output-dir ai_output --max-frames 15
```

---

## 📊 Measured Performance Profiling Benchmark

- **Test Video**: `sample_video.mp4` (640x480 @ 15.0 FPS)
- **Processed Frames**: 15 / 30
- **Elapsed Execution Time**: 8.04 seconds
- **Measured Frame Rate**: **1.86 FPS** *(CPU execution)*
- **Avg Frame Inference Time**: **528.0 ms/frame**
- **JSON Result Output**: [ai_output/result_sample_video.json](file:///c:/Users/mayur/OneDrive/Desktop/SIH/ai_output/result_sample_video.json)
- **Annotated Video Output**: [ai_output/annotated_sample_video.mp4](file:///c:/Users/mayur/OneDrive/Desktop/SIH/ai_output/annotated_sample_video.mp4)
