# SIH26124 – Mobile Urban Intelligence Platform

> **Smart India Hackathon 2026 Project (SIH26124)**  
> AI-powered mobile urban road and infrastructure sensing platform converting public transport buses into intelligent sensing units.

---

## 📸 Overview

Public transport buses traverse arterial roads across a city multiple times daily. **SIH26124** leverages existing bus fleets as mobile AI sensing units equipped with dash-cameras, edge compute devices (Raspberry Pi / Jetson), and GPS modules.

Instead of streaming expensive, continuous video back to municipal servers, edge devices run real-time computer vision (Ultralytics YOLOv8 + DefectTracker) to detect road defects (potholes), estimate traffic density, analyze traffic signal status, and assess zebra crossing conditions locally. Light spatial-temporal telemetry events are queued via SQLite and transmitted to a central **Spring Boot + PostgreSQL/PostGIS** backend, where spatial clustering merges multi-bus observations into persistent, prioritized **Incidents** displayed on an interactive **React + Leaflet GIS Dashboard** for municipal work order dispatch.

---

## ⚠️ Problem

Municipalities face major challenges in maintaining road infrastructure due to delayed defect reporting, manual inspection inefficiencies, and high operational costs. Continuous video streaming from hundreds of municipal vehicles is bandwidth-heavy and privacy-invasive. 

**SIH26124** addresses this problem by using mobile vehicle sensing and AI to process video feeds at the edge. It detects road defects and urban infrastructure issues automatically, extracting lightweight telemetry events locally and consolidating multi-vehicle observations centrally.

---

## 🧩 Main AI Modules

1. **Pothole Detection (`ai/pothole/`)**: Fine-tuned YOLOv8 model for real-time pothole identification with multi-frame temporal defect tracking (`DefectTracker`).
2. **Traffic Density Estimation (`ai/traffic/`)**: Volumetric vehicle counting (`car`, `bus`, `truck`, `motorcycle`, `bicycle`) using authentic COCO classes to classify road traffic density into `LOW`, `MEDIUM`, or `HIGH`.
3. **Traffic Signal Intelligence (`ai/traffic_signal/`)**: Signal light detection using COCO traffic light class (9) paired with a decoupled HSV state analyzer (`RED`, `YELLOW`, `GREEN`, `OFF`, `UNKNOWN`) and health checks.
4. **Zebra Crossing Condition Detection (`ai/zebra_crossing/`)**: Object detection model classifying zebra crossings into `FADED_ZEBRA_CROSSING` vs `GOOD_ZEBRA_CROSSING`.
5. **Unified Road Intelligence Pipeline (`ai/road_intelligence.py`)**: Frame-by-frame processing engine that runs perception modules, profile inference latencies, records annotated video output, and outputs structured JSON summaries.

---

## 🏗️ Architecture

```
Camera / Video Stream (.mp4 / Dash-cam)
                 ↓
      OpenCV / Ultralytics YOLOv8
                 ↓
     Object Detection & Multi-Frame Tracking
                 ↓
    GPS / Telemetry Provider (NMEA / Mock)
                 ↓
   SQLite Offline Telemetry Queue (Edge Caching)
                 ↓
    REST API (Java 21 + Spring Boot)
                 ↓
    PostgreSQL / PostGIS Spatial Database
                 ↓
  React 18 + Leaflet GIS Command Dashboard
```

---

## 🛠️ Technologies

- **Python** (AI Perception Engine, Edge Processing, Scripting)
- **YOLOv8 / Ultralytics** (Real-time Object Detection Models)
- **OpenCV** (Video Feed Processing & Frame Drawing)
- **Java 21** (Backend REST API)
- **Spring Boot** (Backend Microservice Framework)
- **PostgreSQL** (Relational Spatial Database Store)
- **PostGIS** (Geospatial Indexing & Multi-Bus Clustering)
- **React 18** (Command Center UI Frontend)
- **TypeScript** (Frontend Static Typing)
- **Vite** (Frontend Build Tooling)
- **Leaflet** (Interactive GIS Mapping & Marker Rendering)
- **SQLite** (Edge Offline Telemetry Queue)

---

## 📊 ML Baseline Results

The following table summarizes the current held-out baseline evaluation metrics for trained models on test dataset splits:

### 1. Pothole Detection Model
- **Test Set Size**: 246 images
- **Precision**: 86.5%
- **Recall**: 75.8%
- **mAP@0.5**: 81.5%

### 2. Zebra Crossing Condition Model (Baseline)
- **Test Set Size**: 210 images
- **Overall mAP@0.5**: 50.3%
- **Good Crossing (`GOOD_ZEBRA_CROSSING`) mAP@0.5**: 86.4%
- **Faded Crossing (`FADED_ZEBRA_CROSSING`) mAP@0.5**: 14.2%
- **Faded Crossing Recall**: 13.3%

> *Note: These figures represent current initial baseline results.*

---

## ⚠️ Current Limitations

1. **Dataset Imbalance for Faded Zebra Crossings**: Faded zebra crossing detection currently exhibits lower recall and mAP due to class imbalance in the training data (significantly fewer faded examples compared to clear, good-condition crossings).
2. **Missing Zebra Crossing Logic**: Missing zebra crossing detection should eventually rely on contextual/temporal map matching (e.g. comparing GPS coordinates against municipal GIS baseline maps) rather than relying on a simplistic assumption that "no YOLO detection = missing crossing."

---

## 🔮 Future Work

- [ ] Expand and balance the faded zebra crossing dataset to boost minority class recall.
- [ ] Retrain and evaluate the zebra crossing model with augmented edge cases.
- [ ] Integrate fine-tuned zebra crossing model into the unified `road_intelligence.py` pipeline.
- [ ] Connect live NMEA hardware GPS/telemetry feed to edge agent.
- [ ] Complete end-to-end backend integration with Spring Boot & PostGIS.
- [ ] Finalize React + Leaflet GIS Command Center live dashboard UI.
- [ ] Implement RTSP / camera live stream ingestion on Raspberry Pi.
- [ ] Execute complete end-to-end system integration testing across edge, server, and web dashboard.

---

## 📂 Repository Layout

```
SIH/
├── README.md                   # Repository documentation
├── ARCHITECTURE.md             # In-depth system architecture & mathematical formulation
├── ROADMAP.md                  # Development roadmap & milestone verification
├── docker-compose.yml          # Containerized orchestration layout
├── .gitignore                  # Git exclusion configuration
│
├── ai/                         # Perception Layer
│   ├── pothole/                # Pothole Detector & model handlers
│   ├── traffic/                # Traffic Density Estimator
│   ├── traffic_signal/         # Traffic Signal Intelligence module
│   ├── zebra_crossing/         # Zebra Crossing detector interface
│   ├── tests/                  # Automated test suite (64/64 passing)
│   └── road_intelligence.py    # Unified Video Pipeline Engine
│
├── edge/                       # Edge Agent & Telemetry Software (Python)
│   └── telemetry/              # GPS Providers & SQLite Offline Queue
│
├── backend/                    # Core REST API & Spatial Engine (Java 21 / Spring Boot)
├── frontend/                   # Municipal GIS Dashboard (React 18 + TypeScript + Vite)
├── docs/                       # System documentation & setup guides
└── scripts/                    # Deployment, dataset processing, and simulation tools
```
