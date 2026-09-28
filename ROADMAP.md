# Development Roadmap: SIH26124 Mobile Urban Intelligence Platform

This roadmap defines the phase-by-phase implementation plan for building SIH26124. Each phase delivers a verifiable, modular milestone.

---

## 🚩 Milestone Overview

```
Phase 1 (AI Vision Prototype) ➔ Phase 2 (Edge Agent & GPS) ➔ Phase 3 (Backend Ingestion & DB)
                                                                       │
Phase 6 (Integration & Test) ⬅ Phase 5 (GIS Dashboard) ⬅ Phase 4 (Spatial Merging & Priority)
```

---

## 📌 Phase 1: AI Vision & Object Tracking Prototype (AI MVP)
**Goal**: Build a standalone Python Computer Vision module that detects potholes from video/camera feeds, tracks detected defects across consecutive frames, and aggregates temporal bounding boxes into single localized defect events.

- [ ] Setup Python environment (`requirements.txt`, PyTorch, OpenCV, Ultralytics YOLOv8/v11, Supervision / ByteTrack).
- [ ] Implement synthetic/pre-trained Pothole detector module (`ai/inference.py`).
- [ ] Implement single-camera object tracking (`ai/tracker.py`) to assign persistent `track_id` to defects across video frames.
- [ ] Implement edge event temporal aggregator (`ai/aggregator.py`) to collapse multiple frame detections into 1 aggregated event upon track exit.
- [ ] Create CLI test harness (`ai/test_video.py`) that accepts test video files and outputs aggregated JSON event payloads.
- **Verification**: Run `python ai/test_video.py --source sample.mp4` and verify frame-by-frame detections produce 1 output event per pothole without duplication.

---

## 📌 Phase 2: Edge Software & Telemetry Agent
**Goal**: Build the complete Raspberry Pi / Edge agent capable of reading GPS telemetry, managing an offline queue, and posting event telemetry to the backend.

- [ ] Implement serial GPS NMEA reader (`edge/gps_reader.py`) with fallback to mock GPS coordinates for local development.
- [ ] Build local SQLite offline buffer queue (`edge/offline_queue.py`) for persistent event storage during network outages.
- [ ] Build network status monitor and background sync worker (`edge/sync_worker.py`) with exponential backoff retry logic.
- [ ] Build edge configuration module (`edge/config.py`) loading from `.env`.
- [ ] Integrate AI pipeline with GPS & Telemetry client into a unified Edge daemon script (`edge/main.py`).
- **Verification**: Simulate network failure (disconnect Wi-Fi/Ethernet) while running `edge/main.py`, trigger 5 synthetic detections, reconnect network, and verify automatic queue flush to endpoint.

---

## 📌 Phase 3: Backend Core Engine & Database
**Goal**: Implement the Java Spring Boot REST backend with PostgreSQL + PostGIS integration for receiving telemetry and managing core entities.

- [ ] Initialize Spring Boot 3.x project structure with Gradle/Maven (`backend/`).
- [ ] Configure PostgreSQL + PostGIS spatial database connection and JPA entities (`BusDevice`, `Observation`, `Incident`, `WorkOrder`).
- [ ] Implement database migrations (Flyway / Liquibase) for GIS spatial schema and spatial indexes.
- [ ] Build secure device telemetry ingestion endpoint (`POST /api/v1/telemetry/observations`).
- [ ] Implement device authentication (API key / HMAC / Token validation).
- [ ] Implement basic CRUD REST APIs for Devices and Observations.
- **Verification**: Run unit & integration tests (`mvn test`), post test telemetry payload via `curl`/Postman, verify PostGIS `GEOMETRY` insertion.

---

## 📌 Phase 4: Geospatial Clustering & Multi-Bus Priority Engine
**Goal**: Implement backend intelligent processing to deduplicate multi-bus observations into persistent Incidents and compute dynamic priority scores.

- [ ] Implement PostGIS spatial query repository (`ObservationRepository`, `IncidentRepository`) utilizing `ST_DWithin` spatial distance matching.
- [ ] Implement Spatial Clustering Engine (`SpatialClusteringService`) to merge observations within 10m radius into single `Incident` entities.
- [ ] Implement centroid recalculation logic for updated incidents.
- [ ] Implement multi-factor Priority Engine (`PriorityCalculationService`) computing severity scores (`LOW`, `MODERATE`, `CRITICAL`) based on defect type, confidence, size, observation count, and persistence.
- [ ] Add event verification threshold logic (`UNVERIFIED` ➔ `VERIFIED`).
- **Verification**: Send 3 simulated observations from different buses within 5 meters of each other; verify only 1 `Incident` is generated with `observation_count = 3` and recalculated priority score.

---

## 📌 Phase 5: Municipal GIS Dashboard & Work Order Portal
**Goal**: Build a modern, responsive React + TypeScript GIS dashboard with interactive OpenStreetMap/Leaflet integration for municipal engineers.

- [ ] Initialize React + TypeScript application with Vite (`frontend/`).
- [ ] Set up Leaflet map container (`react-leaflet`) with custom marker icons for severity levels (Red, Amber, Green).
- [ ] Implement real-time / polled incident cluster view on map.
- [ ] Build Incident Detail Modal showing observation history, confidence stats, cropped patch imagery, and priority breakdown.
- [ ] Build Municipal Work Order management board (Kanban / Table view) for assigning contractors and tracking repair status (`ASSIGNED` ➔ `IN_PROGRESS` ➔ `RESOLVED`).
- [ ] Integrate JWT user authentication (`Admin`, `Municipal Inspector`).
- **Verification**: Open frontend UI in browser, verify map markers render correctly from backend API, test updating work order status to `COMPLETED`.

---

## 📌 Phase 6: End-to-End System Integration, Dockerization & Validation
**Goal**: Containerize the complete platform, run end-to-end simulation test suites, verify privacy compliance, and compile final project documentation.

- [ ] Write `Dockerfile` for Edge Agent, Backend Service, and Frontend UI.
- [ ] Create root `docker-compose.yml` orchestrating PostgreSQL/PostGIS, Backend API, Frontend Web, and Edge Simulator.
- [ ] Create an Edge Bus Simulator script (`scripts/bus_simulator.py`) to simulate 5 buses driving along municipal routes generating telemetry.
- [ ] Conduct privacy audit (verify no raw video stored, ensure face/plate privacy controls).
- [ ] Run full system end-to-end integration tests.
- **Verification**: Execute `docker-compose up`, start `bus_simulator.py`, view real-time incident generation on GIS dashboard.
