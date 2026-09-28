# SIH26124 System Architecture

This document describes the high-level software architecture, data flow, and module boundaries of the SIH26124 Mobile Urban Intelligence Platform.

---

## Data Pipeline Flow

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

## System Components

### 1. Edge Perception Layer (`ai/`)
- **Pipeline Orchestrator (`ai/road_intelligence.py`)**: Ingests video frames, passes frames to perception modules, profiles latencies, and aggregates detections.
- **Pothole Detection (`ai/pothole/`)**: Multi-frame detection and temporal defect tracking (`DefectTracker`).
- **Traffic Density Estimator (`ai/traffic/`)**: Volumetric vehicle counting using COCO vehicle classes.
- **Traffic Signal Intelligence (`ai/traffic_signal/`)**: COCO traffic light detection paired with HSV state analysis.
- **Zebra Crossing Detector (`ai/zebra_crossing/`)**: Detects condition of zebra crossings (`FADED_ZEBRA_CROSSING` vs `GOOD_ZEBRA_CROSSING`).

### 2. Edge Agent & Telemetry (`edge/`)
- **GPS Telemetry Abstraction**: `NMEAGPSProvider` for hardware serial GPS modules and `MockGPSProvider` for testing.
- **SQLite Offline Queue (`OfflineEventQueue`)**: Caches telemetry events locally during cellular dropouts and flushes data upon network reconnection.

### 3. Central Backend (`backend/`)
- **REST API**: Built with Java 21 and Spring Boot.
- **Geospatial Engine**: PostgreSQL + PostGIS database performing spatial clustering and multi-bus corroboration to generate prioritized municipal incidents.

### 4. Web Command Dashboard (`frontend/`)
- **GIS Mapping**: React 18, TypeScript, Vite, and Leaflet rendering incident markers, severity halos, and work order management tools.
