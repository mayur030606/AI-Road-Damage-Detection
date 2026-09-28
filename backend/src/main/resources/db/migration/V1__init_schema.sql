-- SIH26124 PostGIS Database Schema Initializer

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id VARCHAR(64) PRIMARY KEY,
    bus_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    detection_status VARCHAR(32) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    location GEOMETRY(Point, 4326),
    gps_fix_status VARCHAR(16) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    bounding_box VARCHAR(255),
    severity VARCHAR(16) NOT NULL,
    source VARCHAR(128),
    metadata TEXT,
    lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'DETECTED',
    observation_count INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telemetry_events_location ON telemetry_events USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_bus_id ON telemetry_events (bus_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_event_type ON telemetry_events (event_type);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_lifecycle_status ON telemetry_events (lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_severity ON telemetry_events (severity);
