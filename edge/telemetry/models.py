"""
Unified Telemetry Event Data Model for SIH26124 Edge Telemetry Layer.

Combines AI perception observations with geographic coordinates, device telemetry,
severity ratings, and timestamp metadata into standardized JSON payloads.
"""

from dataclasses import dataclass, field
import datetime
import json
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class UnifiedTelemetryEvent:
    """
    Standardized Geo-Tagged Telemetry Event payload emitted by bus sensing units.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = "BUS-EDGE-001"
    event_type: str = "POTHOLE"  # "POTHOLE", "ZEBRA_CROSSING", "TRAFFIC_DENSITY", "TRAFFIC_SIGNAL"
    detection_status: str = "DETECTED"
    confidence: float = 1.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_fix_status: str = "NO_FIX"  # "NO_FIX", "2D_FIX", "3D_FIX", "SIMULATED", "INVALID", "STALE"
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    bounding_box: Optional[List[float]] = None
    severity: str = "INFO"  # "LOW", "MEDIUM", "HIGH", "CRITICAL", "INFO"
    source: str = "camera_stream"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert telemetry event to dictionary."""
        return {
            "event_id": self.event_id,
            "device_id": self.device_id,
            "bus_id": self.device_id,  # Alias for bus_id compatibility
            "event_type": self.event_type,
            "detection_status": self.detection_status,
            "confidence": round(float(self.confidence), 4),
            "latitude": round(float(self.latitude), 6) if self.latitude is not None else None,
            "longitude": round(float(self.longitude), 6) if self.longitude is not None else None,
            "gps_fix_status": self.gps_fix_status,
            "timestamp": self.timestamp,
            "bounding_box": [round(x, 2) for x in self.bounding_box] if self.bounding_box is not None else None,
            "severity": self.severity,
            "source": self.source,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize telemetry event to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedTelemetryEvent":
        """Construct UnifiedTelemetryEvent from dictionary."""
        device_id = data.get("device_id") or data.get("bus_id") or "BUS-EDGE-001"
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            device_id=device_id,
            event_type=data.get("event_type", "POTHOLE"),
            detection_status=data.get("detection_status", "DETECTED"),
            confidence=float(data.get("confidence", 1.0)),
            latitude=float(data["latitude"]) if data.get("latitude") is not None else None,
            longitude=float(data["longitude"]) if data.get("longitude") is not None else None,
            gps_fix_status=data.get("gps_fix_status", "NO_FIX"),
            timestamp=data.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            bounding_box=data.get("bounding_box"),
            severity=data.get("severity", "INFO"),
            source=data.get("source", "camera_stream"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "UnifiedTelemetryEvent":
        """Deserialize UnifiedTelemetryEvent from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
