package com.sih26124.backend.dto;

import com.sih26124.backend.model.EventLifecycleStatus;
import com.sih26124.backend.model.EventSeverity;
import com.sih26124.backend.model.TelemetryEventEntity;

import java.util.List;

public class EventResponseDto {

    private String eventId;
    private String busId;
    private String eventType;
    private String detectionStatus;
    private Double confidence;
    private Double latitude;
    private Double longitude;
    private String gpsFixStatus;
    private String timestamp;
    private String boundingBox;
    private EventSeverity severity;
    private String source;
    private String metadata;
    private EventLifecycleStatus lifecycleStatus;
    private Integer observationCount;
    private String createdAt;

    public static EventResponseDto fromEntity(TelemetryEventEntity entity) {
        EventResponseDto dto = new EventResponseDto();
        dto.setEventId(entity.getEventId());
        dto.setBusId(entity.getBusId());
        dto.setEventType(entity.getEventType());
        dto.setDetectionStatus(entity.getDetectionStatus());
        dto.setConfidence(entity.getConfidence());
        dto.setLatitude(entity.getLatitude());
        dto.setLongitude(entity.getLongitude());
        dto.setGpsFixStatus(entity.getGpsFixStatus());
        dto.setTimestamp(entity.getTimestamp() != null ? entity.getTimestamp().toString() : null);
        dto.setBoundingBox(entity.getBoundingBox());
        dto.setSeverity(entity.getSeverity());
        dto.setSource(entity.getSource());
        dto.setMetadata(entity.getMetadata());
        dto.setLifecycleStatus(entity.getLifecycleStatus());
        dto.setObservationCount(entity.getObservationCount());
        dto.setCreatedAt(entity.getCreatedAt() != null ? entity.getCreatedAt().toString() : null);
        return dto;
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

    public String getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(String createdAt) {
        this.createdAt = createdAt;
    }
}
