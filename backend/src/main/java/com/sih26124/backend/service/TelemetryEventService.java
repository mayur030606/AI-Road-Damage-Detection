package com.sih26124.backend.service;

import com.sih26124.backend.dto.EventCreateRequestDto;
import com.sih26124.backend.dto.EventResponseDto;
import com.sih26124.backend.exception.InvalidEventDataException;
import com.sih26124.backend.exception.ResourceNotFoundException;
import com.sih26124.backend.model.EventLifecycleStatus;
import com.sih26124.backend.model.EventSeverity;
import com.sih26124.backend.model.TelemetryEventEntity;
import com.sih26124.backend.repository.TelemetryEventRepository;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.GeometryFactory;
import org.locationtech.jts.geom.Point;
import org.locationtech.jts.geom.PrecisionModel;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class TelemetryEventService {

    private final TelemetryEventRepository repository;
    private final MultiBusCorroborationService corroborationService;
    private final GeometryFactory geometryFactory = new GeometryFactory(new PrecisionModel(), 4326);

    public TelemetryEventService(TelemetryEventRepository repository, MultiBusCorroborationService corroborationService) {
        this.repository = repository;
        this.corroborationService = corroborationService;
    }

    public EventResponseDto createEvent(EventCreateRequestDto dto) {
        String busId = dto.getResolvedBusId();
        if (busId == null || busId.isBlank()) {
            throw new InvalidEventDataException("busId or deviceId is required");
        }

        // Check if multi-bus corroboration matches an existing spatial candidate
        Optional<TelemetryEventEntity> corroboratedOpt = corroborationService.corroboratWithExistingEvents(
                dto.getEventType(), busId, dto.getLatitude(), dto.getLongitude()
        );

        if (corroboratedOpt.isPresent()) {
            return EventResponseDto.fromEntity(corroboratedOpt.get());
        }

        TelemetryEventEntity entity = new TelemetryEventEntity();
        entity.setEventId(dto.getEventId() != null ? dto.getEventId() : UUID.randomUUID().toString());
        entity.setBusId(busId);
        entity.setEventType(dto.getEventType().toUpperCase());
        entity.setDetectionStatus(dto.getDetectionStatus() != null ? dto.getDetectionStatus() : "DETECTED");
        entity.setConfidence(dto.getConfidence());
        entity.setLatitude(dto.getLatitude());
        entity.setLongitude(dto.getLongitude());
        entity.setGpsFixStatus(dto.getGpsFixStatus() != null ? dto.getGpsFixStatus() : "NO_FIX");

        if (dto.getLatitude() != null && dto.getLongitude() != null) {
            Point point = geometryFactory.createPoint(new Coordinate(dto.getLongitude(), dto.getLatitude()));
            entity.setLocation(point);
        }

        try {
            entity.setTimestamp(Instant.parse(dto.getTimestamp()));
        } catch (Exception e) {
            entity.setTimestamp(Instant.now());
        }

        if (dto.getBoundingBox() != null) {
            entity.setBoundingBox(dto.getBoundingBox().toString());
        }

        try {
            entity.setSeverity(dto.getSeverity() != null ? EventSeverity.valueOf(dto.getSeverity().toUpperCase()) : EventSeverity.INFO);
        } catch (Exception e) {
            entity.setSeverity(EventSeverity.INFO);
        }

        entity.setSource(dto.getSource() != null ? dto.getSource() : "camera_stream");
        if (dto.getMetadata() != null) {
            entity.setMetadata(dto.getMetadata().toString());
        }

        TelemetryEventEntity saved = repository.save(entity);
        return EventResponseDto.fromEntity(saved);
    }

    public EventResponseDto getEventById(String id) {
        TelemetryEventEntity entity = repository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Telemetry event not found with ID: " + id));
        return EventResponseDto.fromEntity(entity);
    }

    public List<EventResponseDto> getAllEvents(String type, String status, String severity) {
        List<TelemetryEventEntity> list;
        if (type != null && !type.isBlank()) {
            list = repository.findByEventType(type.toUpperCase());
        } else if (severity != null && !severity.isBlank()) {
            list = repository.findBySeverity(EventSeverity.valueOf(severity.toUpperCase()));
        } else if (status != null && !status.isBlank()) {
            list = repository.findByLifecycleStatus(EventLifecycleStatus.valueOf(status.toUpperCase()));
        } else {
            list = repository.findAll();
        }

        return list.stream().map(EventResponseDto::fromEntity).collect(Collectors.toList());
    }

    public List<EventResponseDto> getNearbyEvents(double latitude, double longitude, double radiusMeters) {
        List<TelemetryEventEntity> list;
        try {
            list = repository.findNearbyNative(latitude, longitude, radiusMeters);
        } catch (Exception e) {
            // Fallback bounding box search for H2 test environments
            double latDelta = radiusMeters / 111000.0;
            double lonDelta = radiusMeters / (111000.0 * Math.cos(Math.toRadians(latitude)));
            list = repository.findWithinBoundingBox(
                    latitude - latDelta, longitude - lonDelta,
                    latitude + latDelta, longitude + lonDelta
            );
        }
        return list.stream().map(EventResponseDto::fromEntity).collect(Collectors.toList());
    }

    public EventResponseDto updateLifecycleStatus(String id, EventLifecycleStatus newStatus) {
        TelemetryEventEntity entity = repository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Telemetry event not found with ID: " + id));

        entity.setLifecycleStatus(newStatus);
        TelemetryEventEntity updated = repository.save(entity);
        return EventResponseDto.fromEntity(updated);
    }
}
