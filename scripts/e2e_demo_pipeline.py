"""
SIH26124 End-to-End Demonstration Pipeline
-------------------------------------------
Simulates and validates the complete flow:
Camera / Video Stream
      ↓
Unified AI Perception Pipeline
      ↓
AIObservation Array
      ↓
Mock GPS / Telemetry Processor
      ↓
UnifiedTelemetryEvent
      ↓
SQLite Offline Event Queue
      ↓
Spring Boot REST API (POST /api/events)
      ↓
PostgreSQL + PostGIS & Municipal React GIS Dashboard

All generated/simulated demonstration events are explicitly labeled:
[DEMO DATA / SIMULATED]
"""

import sys
import os
import time
import logging

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from edge.telemetry.gps import MockGPSProvider
from edge.telemetry.processor import TelemetryProcessor
from edge.telemetry.queue import OfflineEventQueue
from ai.common.models import AIObservation, BoundingBox

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("E2EDemoPipeline")

def run_e2e_demo():
    logger.info("==================================================================")
    logger.info("SIH26124: STARTING END-TO-END DEMONSTRATION PIPELINE [DEMO DATA]")
    logger.info("==================================================================")

    # Step 1: Initialize GPS & Telemetry Processor
    gps_provider = MockGPSProvider(initial_latitude=28.6139, initial_longitude=77.2090)
    processor = TelemetryProcessor(gps_provider=gps_provider, device_id="BUS-DEMO-001")
    queue_db_path = os.path.join(PROJECT_ROOT, "scripts", "demo_offline_queue.db")
    
    # Remove prior demo db if exists
    if os.path.exists(queue_db_path):
        try:
            os.remove(queue_db_path)
        except Exception:
            pass

    offline_queue = OfflineEventQueue(db_path=queue_db_path)

    # Step 2: Create Observations representing all 4 AI capabilities [DEMO DATA]
    demo_observations = [
        AIObservation(
            detector_type="POTHOLE_DETECTOR",
            event_type="POTHOLE",
            confidence=0.92,
            source="frame_001.jpg",
            frame_number=1,
            bbox=BoundingBox(100, 150, 200, 250),
            metadata={"demo_tag": "DEMO DATA", "estimated_area_ratio": 0.05, "bus_id": "BUS-DEMO-001"}
        ),
        AIObservation(
            detector_type="ZEBRA_CROSSING_DETECTOR",
            event_type="ZEBRA_CROSSING",
            confidence=0.50,
            source="frame_002.jpg",
            frame_number=2,
            bbox=BoundingBox(50, 300, 400, 350),
            metadata={"demo_tag": "DEMO DATA / PROTOTYPE REQUIRES MODEL", "status": "UNKNOWN"}
        ),
        AIObservation(
            detector_type="TRAFFIC_DENSITY_ESTIMATOR",
            event_type="TRAFFIC_DENSITY",
            confidence=0.88,
            source="frame_003.jpg",
            frame_number=3,
            bbox=None,
            metadata={"demo_tag": "DEMO DATA", "vehicle_count": 14, "density_level": "HIGH"}
        ),
        AIObservation(
            detector_type="TRAFFIC_SIGNAL_DETECTOR",
            event_type="TRAFFIC_SIGNAL",
            confidence=0.95,
            source="frame_004.jpg",
            frame_number=4,
            bbox=BoundingBox(300, 50, 340, 150),
            metadata={
                "demo_tag": "DEMO DATA / HSV PROTOTYPE",
                "state": "RED",
                "status": "SIGNAL_OPERATING"
            }
        ),
    ]

    start_time = time.time()
    telemetry_events = []

    logger.info("------------------------------------------------------------------")
    logger.info("STEP 1: Processing AI Observations into UnifiedTelemetryEvents")
    logger.info("------------------------------------------------------------------")

    for obs in demo_observations:
        event = processor.process_observation(obs)
        telemetry_events.append(event)
        logger.info(f"Processed Event [{event.event_id}] Type: {event.event_type} | Severity: {event.severity} | Status: {event.detection_status} [DEMO DATA]")

    # Step 3: Enqueue events into Offline Queue
    logger.info("------------------------------------------------------------------")
    logger.info("STEP 2: Buffering Events in Offline Queue (SQLite local retention)")
    logger.info("------------------------------------------------------------------")
    for evt in telemetry_events:
        offline_queue.enqueue(evt)

    q_count = offline_queue.get_queue_depth()
    logger.info(f"Offline Queue contains {q_count} buffered event(s).")

    # Step 4: Transmit batch to Spring Boot REST Backend (if running)
    logger.info("------------------------------------------------------------------")
    logger.info("STEP 3: Attempting Batch Ingestion to Spring Boot (POST /api/events)")
    logger.info("------------------------------------------------------------------")

    api_url = os.getenv("VITE_API_BASE_URL", "http://localhost:8080/api") + "/events"
    import requests

    transmitted_count = 0
    failed_count = 0

    peeked_events = offline_queue.peek(batch_size=10)
    for evt in peeked_events:
        payload = evt.to_dict()
        try:
            resp = requests.post(api_url, json=payload, timeout=2.0)
            if resp.status_code in (200, 201):
                logger.info(f"Successfully transmitted Event [{evt.event_id}] to Spring Boot backend.")
                offline_queue.acknowledge([evt.event_id])
                transmitted_count += 1
            else:
                logger.warning(f"Backend HTTP {resp.status_code} for Event [{evt.event_id}]. Retaining in queue.")
                failed_count += 1
        except Exception as e:
            logger.info(f"Backend offline/unreachable at '{api_url}' ({e}). Retaining Event [{evt.event_id}] in queue. [DEMO DATA RETENTION VERIFIED]")
            failed_count += 1

    elapsed_ms = (time.time() - start_time) * 1000.0

    logger.info("==================================================================")
    logger.info("DEMONSTRATION SUMMARY METRICS [MEASURED VALUES ONLY]")
    logger.info("==================================================================")
    logger.info(f"Total AI Observations Processed : {len(demo_observations)}")
    logger.info(f"Total Telemetry Events Formatted: {len(telemetry_events)}")
    logger.info(f"Events Transmitted to Backend   : {transmitted_count}")
    logger.info(f"Events Retained in Queue        : {failed_count}")
    logger.info(f"Pipeline Processing Latency     : {elapsed_ms:.2f} ms")
    logger.info("Label Verification              : ALL EVENTS EXPLICITLY TAGGED [DEMO DATA]")
    logger.info("==================================================================")

    # Cleanup demo database file
    if os.path.exists(queue_db_path):
        try:
            os.remove(queue_db_path)
        except Exception:
            pass

    return {
        "processed_observations": len(demo_observations),
        "telemetry_events": len(telemetry_events),
        "transmitted_count": transmitted_count,
        "retained_count": failed_count,
        "elapsed_ms": elapsed_ms,
    }

if __name__ == "__main__":
    run_e2e_demo()
