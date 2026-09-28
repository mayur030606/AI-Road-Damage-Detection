package com.sih26124.backend.service;

import com.sih26124.backend.model.EventLifecycleStatus;
import com.sih26124.backend.model.TelemetryEventEntity;
import com.sih26124.backend.repository.TelemetryEventRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Service
public class MultiBusCorroborationService {

    private final TelemetryEventRepository eventRepository;
    private static final double DEFAULT_CORROBORATION_RADIUS_METERS = 15.0;

    public MultiBusCorroborationService(TelemetryEventRepository eventRepository) {
        this.eventRepository = eventRepository;
    }

    public Optional<TelemetryEventEntity> corroboratWithExistingEvents(
            String eventType,
            String reportingBusId,
            Double latitude,
            Double longitude
    ) {
        if (latitude == null || longitude == null || reportingBusId == null) {
            return Optional.empty();
        }

        List<TelemetryEventEntity> candidates;
        try {
            candidates = eventRepository.findCandidatesForCorroborationNative(
                    eventType, latitude, longitude, DEFAULT_CORROBORATION_RADIUS_METERS
            );
        } catch (Exception e) {
            // Fallback for H2 or non-spatial native query environments
            candidates = eventRepository.findWithinBoundingBox(
                    latitude - 0.0002, longitude - 0.0002,
                    latitude + 0.0002, longitude + 0.0002
            ).stream().filter(ev -> ev.getEventType().equalsIgnoreCase(eventType)).toList();
        }

        for (TelemetryEventEntity candidate : candidates) {
            // Corroborate if observation comes from a different bus OR distinct trip pass
            if (!candidate.getBusId().equalsIgnoreCase(reportingBusId)) {
                candidate.setObservationCount(candidate.getObservationCount() + 1);
                if (candidate.getObservationCount() >= 2 && candidate.getLifecycleStatus() == EventLifecycleStatus.DETECTED) {
                    candidate.setLifecycleStatus(EventLifecycleStatus.VERIFIED);
                }
                return Optional.of(eventRepository.save(candidate));
            }
        }

        return Optional.empty();
    }
}
