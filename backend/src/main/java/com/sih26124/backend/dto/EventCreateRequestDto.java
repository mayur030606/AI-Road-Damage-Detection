package com.sih26124.backend.dto;

import jakarta.validation.constraints.*;
import java.util.List;
import java.util.Map;

public class EventCreateRequestDto {

    private String eventId;

    private String busId;
    private String deviceId;

    @NotBlank(message = "event_type is required")
    private String eventType;

    private String detectionStatus;

    @NotNull(message = "confidence is required")
    @DecimalMin(value = "0.0", message = "confidence must be >= 0.0")
    @DecimalMax(value = "1.0", message = "confidence must be <= 1.0")
    private Double confidence;

    @DecimalMin(value = "-90.0", message = "latitude must be >= -90.0")
    @DecimalMax(value = "90.0", message = "latitude must be <= 90.0")
    private Double latitude;

    @DecimalMin(value = "-180.0", message = "longitude must be >= -180.0")
    @DecimalMax(value = "180.0", message = "longitude must be <= 180.0")
    private Double longitude;

    private String gpsFixStatus;

    @NotBlank(message = "timestamp is required")
    private String timestamp;

    private List<Double> boundingBox;

    private String severity;

    private String source;

    private Map<String, Object> metadata;

    public String getResolvedBusId() {
        if (busId != null && !busId.isBlank()) return busId;
        if (deviceId != null && !deviceId.isBlank()) return deviceId;
        return null;
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

    public String getDeviceId() {
        return deviceId;
    }

    public void setDeviceId(String deviceId) {
        this.deviceId = deviceId;
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

    public String getGpsFixStatus() {
        return gpsFixStatus;
    }

    public void setGpsFixStatus(String gpsFixStatus) {
        this.gpsFixStatus = gpsFixStatus;
    }

    public String getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(String timestamp) {
        this.timestamp = timestamp;
    }

    public List<Double> getBoundingBox() {
        return boundingBox;
    }

    public void setBoundingBox(List<Double> boundingBox) {
        this.boundingBox = boundingBox;
    }

    public String getSeverity() {
        return severity;
    }

    public void setSeverity(String severity) {
        this.severity = severity;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public Map<String, Object> getMetadata() {
        return metadata;
    }

    public void setMetadata(Map<String, Object> metadata) {
        this.metadata = metadata;
    }
}
