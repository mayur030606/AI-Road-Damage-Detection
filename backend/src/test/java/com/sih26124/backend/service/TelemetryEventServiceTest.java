package com.sih26124.backend.service;

import com.sih26124.backend.dto.EventCreateRequestDto;
import com.sih26124.backend.dto.EventResponseDto;
import com.sih26124.backend.exception.InvalidEventDataException;
import com.sih26124.backend.exception.ResourceNotFoundException;
import com.sih26124.backend.model.EventLifecycleStatus;
import com.sih26124.backend.model.TelemetryEventEntity;
import com.sih26124.backend.repository.TelemetryEventRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;

public class TelemetryEventServiceTest {

    private TelemetryEventRepository repository;
    private MultiBusCorroborationService corroborationService;
    private TelemetryEventService service;

    @BeforeEach
    public void setUp() {
        repository = Mockito.mock(TelemetryEventRepository.class);
        corroborationService = Mockito.mock(MultiBusCorroborationService.class);
        service = new TelemetryEventService(repository, corroborationService);
    }

    @Test
    public void testCreateEventMissingBusIdThrowsException() {
        EventCreateRequestDto request = new EventCreateRequestDto();
        request.setEventType("POTHOLE");
        request.setConfidence(0.9);

        assertThrows(InvalidEventDataException.class, () -> service.createEvent(request));
    }

    @Test
    public void testCreateEventSuccess() {
        EventCreateRequestDto request = new EventCreateRequestDto();
        request.setBusId("BUS-99");
        request.setEventType("POTHOLE");
        request.setConfidence(0.85);
        request.setLatitude(18.5204);
        request.setLongitude(73.8567);

        Mockito.when(corroborationService.corroboratWithExistingEvents(any(), any(), any(), any()))
                .thenReturn(Optional.empty());

        Mockito.when(repository.save(any(TelemetryEventEntity.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        EventResponseDto dto = service.createEvent(request);

        assertNotNull(dto);
        assertEqual("BUS-99", dto.getBusId());
        assertEqual("POTHOLE", dto.getEventType());
        assertEqual(0.85, dto.getConfidence());
        assertEqual(EventLifecycleStatus.DETECTED, dto.getLifecycleStatus());
    }

    @Test
    public void testGetEventByIdNotFoundThrowsException() {
        Mockito.when(repository.findById("NON-EXISTENT")).thenReturn(Optional.empty());

        assertThrows(ResourceNotFoundException.class, () -> service.getEventById("NON-EXISTENT"));
    }

    @Test
    public void testUpdateLifecycleStatusSuccess() {
        TelemetryEventEntity entity = new TelemetryEventEntity();
        entity.setEventId("EVT-1");
        entity.setBusId("BUS-1");
        entity.setEventType("POTHOLE");
        entity.setConfidence(0.8);
        entity.setLifecycleStatus(EventLifecycleStatus.DETECTED);

        Mockito.when(repository.findById("EVT-1")).thenReturn(Optional.of(entity));
        Mockito.when(repository.save(any(TelemetryEventEntity.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        EventResponseDto updated = service.updateLifecycleStatus("EVT-1", EventLifecycleStatus.RESOLVED);

        assertEqual(EventLifecycleStatus.RESOLVED, updated.getLifecycleStatus());
    }

    private void assertEqual(Object expected, Object actual) {
        assertEquals(expected, actual);
    }
}
