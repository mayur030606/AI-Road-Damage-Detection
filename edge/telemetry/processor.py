"""
Edge Telemetry Processor for SIH26124.

Couples AI perception observations (Pothole, Zebra Crossing, Traffic Density,
Traffic Signal) with GPS location data, calculates event severity, validates
geographic coordinates, and constructs UnifiedTelemetryEvent payloads.

Traffic-signal observations are filtered so that only confirmed/qualified
possible malfunctions are converted into municipal telemetry events.
Normal signal states are ignored.
AI perception modules remain 100% decoupled from GPS hardware.
"""

import logging
from typing import List, Optional

from ai.common.models import AIObservation, PipelineResult
from edge.telemetry.gps import BaseGPSProvider, GPSLocation, MockGPSProvider
from edge.telemetry.models import UnifiedTelemetryEvent

logger = logging.getLogger("TelemetryProcessor")


class TelemetryProcessor:
    """
    Couples AI observations from perception pipeline with edge bus GPS location.
    """

    def __init__(
        self,
        gps_provider: Optional[BaseGPSProvider] = None,
        device_id: str = "BUS-EDGE-001"
    ):
        """
        Initialize TelemetryProcessor.

        Args:
            gps_provider: Instance of BaseGPSProvider.
                Defaults to MockGPSProvider if None.
            device_id: Identifier for bus edge unit.
        """
        self.device_id = device_id
        self.gps_provider = (
            gps_provider if gps_provider is not None
            else MockGPSProvider()
        )

    def set_gps_provider(self, gps_provider: BaseGPSProvider):
        """Update GPS provider instance dynamically."""
        self.gps_provider = gps_provider

    def process_observation(self, obs: AIObservation) -> UnifiedTelemetryEvent:
        """
        Convert a single AIObservation into a UnifiedTelemetryEvent
        geo-tagged record.
        """

        gps_loc = self.gps_provider.get_location()

        # ---------------------------------------------------------
        # GPS Validation and Handling
        # ---------------------------------------------------------
        lat: Optional[float] = None
        lon: Optional[float] = None
        fix_status = "NO_FIX"

        if gps_loc is not None:

            if gps_loc.is_valid(max_age_seconds=30.0):
                lat = gps_loc.latitude
                lon = gps_loc.longitude
                fix_status = gps_loc.fix_status

            elif gps_loc.fix_status == "STALE":
                lat = gps_loc.latitude
                lon = gps_loc.longitude
                fix_status = "STALE"

            elif gps_loc.fix_status == "INVALID":
                fix_status = "INVALID"

            else:
                fix_status = "NO_FIX"

        # ---------------------------------------------------------
        # Bounding Box
        # ---------------------------------------------------------
        bbox_list = (
            obs.bbox.to_list()
            if obs.bbox is not None
            else None
        )

        # ---------------------------------------------------------
        # Detection Status and Severity
        # ---------------------------------------------------------
        detection_status = self._derive_detection_status(obs)
        severity = self._calculate_severity(obs)

        # ---------------------------------------------------------
        # Metadata
        # ---------------------------------------------------------
        metadata = dict(obs.metadata) if obs.metadata else {}

        metadata["detector_type"] = obs.detector_type

        if gps_loc is not None and not gps_loc.is_valid():
            metadata["gps_warning"] = (
                f"GPS fix invalid or missing "
                f"(status: {gps_loc.fix_status})"
            )

        # ---------------------------------------------------------
        # Construct Unified Telemetry Event
        # ---------------------------------------------------------
        event = UnifiedTelemetryEvent(
            device_id=self.device_id,
            event_type=self._map_event_type(obs),
            detection_status=detection_status,
            confidence=obs.confidence,
            latitude=lat,
            longitude=lon,
            gps_fix_status=fix_status,
            timestamp=obs.timestamp,
            bounding_box=bbox_list,
            severity=severity,
            source=obs.source,
            metadata=metadata
        )

        return event

    def process_observations(
        self,
        observations: List[AIObservation]
    ) -> List[UnifiedTelemetryEvent]:
        """
        Convert AI observations into UnifiedTelemetryEvents.

        Traffic-signal observations are handled specially:

        SIGNAL_OPERATING
            -> ignored

        SIGNAL_DETECTED
            -> ignored

        SIGNAL_STATE_UNKNOWN
            -> ignored

        SIGNAL_POSSIBLE_MALFUNCTION
            -> converted into a telemetry event

        Other AI modules continue to be processed normally.
        """

        events: List[UnifiedTelemetryEvent] = []

        for obs in observations:

            # -----------------------------------------------------
            # Traffic Signal Filtering
            # -----------------------------------------------------
            if obs.detector_type == "TRAFFIC_SIGNAL_DETECTOR":

                status = obs.metadata.get("status", "")

                # Only create a municipal incident for a
                # possible/confirmed malfunction.
                if status != "SIGNAL_POSSIBLE_MALFUNCTION":
                    logger.debug(
                        "Ignoring normal traffic signal observation: %s",
                        status
                    )
                    continue

            # -----------------------------------------------------
            # Process all valid observations
            # -----------------------------------------------------
            events.append(
                self.process_observation(obs)
            )

        return events

    def process_pipeline_result(
        self,
        result: PipelineResult
    ) -> List[UnifiedTelemetryEvent]:
        """
        Convert a unified PipelineResult into UnifiedTelemetryEvents.
        """
        return self.process_observations(
            result.observations
        )

    # =============================================================
    # EVENT TYPE MAPPING
    # =============================================================

    @staticmethod
    def _map_event_type(obs: AIObservation) -> str:

        if obs.detector_type == "POTHOLE_DETECTOR":
            return "POTHOLE"

        elif obs.detector_type == "ZEBRA_CROSSING_DETECTOR":
            return "ZEBRA_CROSSING"

        elif obs.detector_type == "TRAFFIC_DENSITY_ESTIMATOR":
            return "TRAFFIC_DENSITY"

        elif obs.detector_type == "TRAFFIC_SIGNAL_DETECTOR":
            return "TRAFFIC_SIGNAL"

        return str(obs.event_type).upper()

    # =============================================================
    # DETECTION STATUS
    # =============================================================

    @staticmethod
    def _derive_detection_status(obs: AIObservation) -> str:

        if obs.detector_type == "POTHOLE_DETECTOR":
            return "POTHOLE_DETECTED"

        elif obs.detector_type == "TRAFFIC_DENSITY_ESTIMATOR":
            return obs.metadata.get(
                "density_level",
                "LOW"
            )

        elif obs.detector_type == "TRAFFIC_SIGNAL_DETECTOR":
            return obs.metadata.get(
                "status",
                "SIGNAL_DETECTED"
            )

        elif obs.detector_type == "ZEBRA_CROSSING_DETECTOR":
            return obs.metadata.get(
                "status",
                "UNKNOWN"
            )

        return str(obs.event_type)

    # =============================================================
    # SEVERITY CALCULATION
    # =============================================================

    @staticmethod
    def _calculate_severity(obs: AIObservation) -> str:
        """
        Calculate event severity based on confidence,
        defect size, density, or signal state.
        """

        # ---------------------------------------------------------
        # POTHOLE
        # ---------------------------------------------------------
        if obs.detector_type == "POTHOLE_DETECTOR":

            area_ratio = obs.metadata.get(
                "estimated_area_ratio",
                0.0
            )

            if obs.confidence > 0.85 or area_ratio > 0.04:
                return "HIGH"

            elif obs.confidence > 0.60:
                return "MEDIUM"

            return "LOW"

        # ---------------------------------------------------------
        # TRAFFIC SIGNAL
        # ---------------------------------------------------------
        elif obs.detector_type == "TRAFFIC_SIGNAL_DETECTOR":

            status = obs.metadata.get(
                "status",
                ""
            )

            if status == "SIGNAL_POSSIBLE_MALFUNCTION":
                return "CRITICAL"

            elif status == "SIGNAL_STATE_UNKNOWN":
                return "MEDIUM"

            return "INFO"

        # ---------------------------------------------------------
        # TRAFFIC DENSITY
        # ---------------------------------------------------------
        elif obs.detector_type == "TRAFFIC_DENSITY_ESTIMATOR":

            level = obs.metadata.get(
                "density_level",
                "LOW"
            )

            if level == "HIGH":
                return "HIGH"

            elif level == "MEDIUM":
                return "MEDIUM"

            return "LOW"

        # ---------------------------------------------------------
        # ZEBRA CROSSING
        # ---------------------------------------------------------
        elif obs.detector_type == "ZEBRA_CROSSING_DETECTOR":

            status = obs.metadata.get(
                "status",
                "UNKNOWN"
            )

            if status == "MISSING":
                return "HIGH"

            elif status == "DEGRADED":
                return "MEDIUM"

            return "INFO"

        # ---------------------------------------------------------
        # DEFAULT
        # ---------------------------------------------------------
        return "INFO"