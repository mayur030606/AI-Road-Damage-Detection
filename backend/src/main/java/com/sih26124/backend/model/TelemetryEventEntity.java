package com.sih26124.backend.model;

import jakarta.persistence.*;
import org.locationtech.jts.geom.Point;

import java.time.Instant;

@Entity
@Table(name = "telemetry_events", indexes = {
    @Index(name = "idx_telemetry_events_bus_id", columnList = "bus_id"),
    @Index(name = "idx_telemetry_events_event_type", columnList = "event_type"),
    @Index(name = "idx_telemetry_events_lifecycle_status", columnList = "lifecycle_status"),
    @Index(name = "idx_telemetry_events_severity", columnList = "severity")
})
public class TelemetryEventEntity {

    @Id
    @Column(name = "event_id", length = 64)
    private String eventId;

    @Column(name = "bus_id", nullable = false, length = 64)
    private String busId;

    @Column(name = "event_type", nullable = false, length = 32)
    private String eventType;

    @Column(name = "detection_status", nullable = false, length = 32)
    private String detectionStatus;

    @Column(name = "confidence", nullable = false)
    private Double confidence;

    @Column(name = "latitude")
    private Double latitude;

    @Column(name = "longitude")
    private Double longitude;

    @Column(name = "location", columnDefinition = "Geometry(Point, 4326)")
    private Point location;

    @Column(name = "gps_fix_status", nullable = false, length = 16)
    private String gpsFixStatus;

    @Column(name = "timestamp", nullable = false)
    private Instant timestamp;

    @Column(name = "bounding_box", length = 255)
    private String boundingBox;

    @Enumerated(EnumType.STRING)
    @Column(name = "severity", nullable = false, length = 16)
    private EventSeverity severity;

    @Column(name = "source", length = 128)
    private String source;

    @Column(name = "metadata", columnDefinition = "TEXT")
    private String metadata;

    @Enumerated(EnumType.STRING)
    @Column(name = "lifecycle_status", nullable = false, length = 32)
    private EventLifecycleStatus lifecycleStatus = EventLifecycleStatus.DETECTED;

    @Column(name = "observation_count", nullable = false)
    private Integer observationCount = 1;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt = Instant.now();

    public TelemetryEventEntity() {
    }

    @PreUpdate
    public void onUpdate() {
        this.updatedAt = Instant.now();
    }

    // Getters and Setters

    public String getEventId() {
        return eventId;
    }

    public void setEventId(String eventId) {
        this.eventId = eventId;
    }

    public String getBusId() {
        return busId;
    }

    public void setBusId(String busId) {
        this.busId = busId;
    }

    public String getEventType() {
        return eventType;
    }

    public void setEventType(String eventType) {
        this.eventType = eventType;
    }

    public String getDetectionStatus() {
        return detectionStatus;
    }

    public void setDetectionStatus(String detectionStatus) {
        this.detectionStatus = detectionStatus;
    }

    public Double getConfidence() {
        return confidence;
    }

    public void setConfidence(Double confidence) {
        this.confidence = confidence;
    }

    public Double getLatitude() {
        return latitude;
    }

    public void setLatitude(Double latitude) {
        this.latitude = latitude;
    }

    public Double getLongitude() {
        return longitude;
    }

    public void setLongitude(Double longitude) {
        this.longitude = longitude;
    }

    public Point getLocation() {
        return location;
    }

    public void setLocation(Point location) {
        this.location = location;
    }

    public String getGpsFixStatus() {
        return gpsFixStatus;
    }

    public void setGpsFixStatus(String gpsFixStatus) {
        this.gpsFixStatus = gpsFixStatus;
    }

    public Instant getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(Instant timestamp) {
        this.timestamp = timestamp;
    }

    public String getBoundingBox() {
        return boundingBox;
    }

    public void setBoundingBox(String boundingBox) {
        this.boundingBox = boundingBox;
    }

    public EventSeverity getSeverity() {
        return severity;
    }

    public void setSeverity(EventSeverity severity) {
        this.severity = severity;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public String getMetadata() {
        return metadata;
    }

    public void setMetadata(String metadata) {
        this.metadata = metadata;
    }

    public EventLifecycleStatus getLifecycleStatus() {
        return lifecycleStatus;
    }

    public void setLifecycleStatus(EventLifecycleStatus lifecycleStatus) {
        this.lifecycleStatus = lifecycleStatus;
    }

    public Integer getObservationCount() {
        return observationCount;
    }

    public void setObservationCount(Integer observationCount) {
        this.observationCount = observationCount;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }
}
