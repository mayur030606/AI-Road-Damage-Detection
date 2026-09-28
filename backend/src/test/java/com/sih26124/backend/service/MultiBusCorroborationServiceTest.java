package com.sih26124.backend.service;

import com.sih26124.backend.model.EventLifecycleStatus;
import com.sih26124.backend.model.TelemetryEventEntity;
import com.sih26124.backend.repository.TelemetryEventRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;

public class MultiBusCorroborationServiceTest {

    private TelemetryEventRepository repository;
    private MultiBusCorroborationService service;

    @BeforeEach
    public void setUp() {
        repository = Mockito.mock(TelemetryEventRepository.class);
        service = new MultiBusCorroborationService(repository);
    }

    @Test
    public void testCorroborationWithDifferentBusIncrementsCountAndVerifies() {
        TelemetryEventEntity existing = new TelemetryEventEntity();
        existing.setEventId("EVT-EXISTING");
        existing.setBusId("BUS-ALPHA");
        existing.setEventType("POTHOLE");
        existing.setObservationCount(1);
        existing.setLifecycleStatus(EventLifecycleStatus.DETECTED);

        Mockito.when(repository.findCandidatesForCorroborationNative(eq("POTHOLE"), eq(18.5204), eq(73.8567), anyDouble()))
                .thenReturn(List.of(existing));

        Mockito.when(repository.save(any(TelemetryEventEntity.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        Optional<TelemetryEventEntity> result = service.corroboratWithExistingEvents("POTHOLE", "BUS-BETA", 18.5204, 73.8567);

        assertTrue(result.isPresent());
        TelemetryEventEntity corroborated = result.get();
        assertEquals(2, corroborated.getObservationCount());
        assertEquals(EventLifecycleStatus.VERIFIED, corroborated.getLifecycleStatus());
    }

    @Test
    public void testCorroborationSameBusDoesNotCorroborate() {
        TelemetryEventEntity existing = new TelemetryEventEntity();
        existing.setEventId("EVT-EXISTING");
        existing.setBusId("BUS-ALPHA");
        existing.setEventType("POTHOLE");
        existing.setObservationCount(1);

        Mockito.when(repository.findCandidatesForCorroborationNative(eq("POTHOLE"), eq(18.5204), eq(73.8567), anyDouble()))
                .thenReturn(List.of(existing));

        Optional<TelemetryEventEntity> result = service.corroboratWithExistingEvents("POTHOLE", "BUS-ALPHA", 18.5204, 73.8567);

        assertTrue(result.isEmpty());
    }
}
