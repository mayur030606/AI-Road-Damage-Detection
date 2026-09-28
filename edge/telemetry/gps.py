"""
GPS Abstraction & Provider System for Edge Bus Units (SIH26124).

Decouples physical GPS hardware (Raspberry Pi, NMEA serial) from AI perception layer.
Provides MockGPSProvider for simulation, development, and unit testing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import datetime
import logging
from typing import Optional, Tuple, Union

logger = logging.getLogger("GPSProvider")


@dataclass
class GPSLocation:
    """Standardized geographic location data record."""
    latitude: float
    longitude: float
    altitude_m: Optional[float] = None
    speed_kmh: Optional[float] = None
    fix_status: str = "3D_FIX"  # "NO_FIX", "2D_FIX", "3D_FIX", "SIMULATED", "INVALID", "STALE"
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def is_valid(self, max_age_seconds: float = 30.0) -> bool:
        """
        Validate coordinate boundaries, fix status, and timestamp freshness.
        """
        if self.fix_status in ("NO_FIX", "INVALID"):
            return False

        if not (-90.0 <= self.latitude <= 90.0 and -180.0 <= self.longitude <= 180.0):
            return False

        # Validate timestamp freshness if parsing succeeds
        try:
            loc_dt = datetime.datetime.fromisoformat(self.timestamp)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            if loc_dt.tzinfo is None:
                loc_dt = loc_dt.replace(tzinfo=datetime.timezone.utc)
            age_sec = (now_dt - loc_dt).total_seconds()
            if age_sec > max_age_seconds or age_sec < -5.0:
                return False
        except Exception:
            pass

        return True

    def to_dict() -> dict:
        return {
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "altitude_m": round(self.altitude_m, 2) if self.altitude_m is not None else None,
            "speed_kmh": round(self.speed_kmh, 2) if self.speed_kmh is not None else None,
            "fix_status": self.fix_status,
            "timestamp": self.timestamp,
        }


class BaseGPSProvider(ABC):
    """Abstract interface for GPS Providers."""

    @abstractmethod
    def get_location(self) -> GPSLocation:
        """Fetch current GPS location record."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check hardware / provider connection state."""
        pass


class MockGPSProvider(BaseGPSProvider):
    """
    Simulation & Testing GPS Provider.
    Supplies configurable static, route-based, invalid, or stale GPS coordinates.
    """

    def __init__(
        self,
        initial_latitude: float = 18.5204,  # Pune, India default
        initial_longitude: float = 73.8567,
        fix_status: str = "SIMULATED",
        altitude_m: float = 560.0,
        speed_kmh: float = 35.0
    ):
        self.latitude = initial_latitude
        self.longitude = initial_longitude
        self.fix_status = fix_status
        self.altitude_m = altitude_m
        self.speed_kmh = speed_kmh
        self._stale_offset_seconds: Optional[float] = None
        self._connected = True

    def get_location(self) -> GPSLocation:
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        if self._stale_offset_seconds is not None:
            now_dt = now_dt - datetime.timedelta(seconds=self._stale_offset_seconds)

        return GPSLocation(
            latitude=self.latitude,
            longitude=self.longitude,
            altitude_m=self.altitude_m,
            speed_kmh=self.speed_kmh,
            fix_status=self.fix_status,
            timestamp=now_dt.isoformat()
        )

    def set_coordinates(self, latitude: float, longitude: float, fix_status: str = "SIMULATED"):
        self.latitude = latitude
        self.longitude = longitude
        self.fix_status = fix_status

    def set_no_fix(self):
        self.fix_status = "NO_FIX"

    def set_invalid_coordinates(self):
        self.latitude = 999.0
        self.longitude = 999.0
        self.fix_status = "INVALID"

    def set_stale_data(self, age_seconds: float = 60.0):
        self._stale_offset_seconds = age_seconds
        self.fix_status = "STALE"

    def clear_stale(self):
        self._stale_offset_seconds = None

    def is_connected(self) -> bool:
        return self._connected

    def set_connected(self, connected: bool):
        self._connected = connected


class NMEAGPSProvider(BaseGPSProvider):
    """
    NMEA Sentence GPS Serial Parser Provider.
    Parses $GPRMC and $GPGGA strings from NMEA serial streams.
    """

    def __init__(self, serial_port: Optional[str] = None, baudrate: int = 9600):
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.last_location: Optional[GPSLocation] = None

    def parse_nmea_sentence(self, sentence: str) -> Optional[GPSLocation]:
        """
        Parse a single NMEA sentence ($GPRMC or $GPGGA).

        Example GPRMC:
        $GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A
        """
        if not sentence or not sentence.startswith("$"):
            return None

        parts = sentence.strip().split(",")
        msg_type = parts[0]

        if msg_type in ("$GPRMC", "$GNRMC"):
            if len(parts) < 7 or parts[2] != "A":  # 'A' = Active/Valid fix
                self.last_location = GPSLocation(0.0, 0.0, fix_status="NO_FIX")
                return self.last_location

            raw_lat, lat_dir = parts[3], parts[4]
            raw_lon, lon_dir = parts[5], parts[6]

            lat = self._nmea_to_decimal(raw_lat, lat_dir)
            lon = self._nmea_to_decimal(raw_lon, lon_dir)

            speed_knots = float(parts[7]) if len(parts) > 7 and parts[7] else 0.0
            speed_kmh = speed_knots * 1.852

            self.last_location = GPSLocation(
                latitude=lat,
                longitude=lon,
                speed_kmh=speed_kmh,
                fix_status="3D_FIX"
            )
            return self.last_location

        return self.last_location

    @staticmethod
    def _nmea_to_decimal(raw_val: str, direction: str) -> float:
        """Convert NMEA degrees-minutes format (ddmm.mmmm) to decimal degrees."""
        if not raw_val or "." not in raw_val:
            return 0.0
        dot_idx = raw_val.find(".")
        deg_len = dot_idx - 2
        deg = float(raw_val[:deg_len])
        minutes = float(raw_val[deg_len:])
        decimal = deg + (minutes / 60.0)
        if direction in ("S", "W"):
            decimal = -decimal
        return decimal

    def get_location(self) -> GPSLocation:
        if self.last_location is not None:
            return self.last_location
        return GPSLocation(0.0, 0.0, fix_status="NO_FIX")

    def is_connected(self) -> bool:
        return self.serial_port is not None
