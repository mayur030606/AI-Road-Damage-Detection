package com.sih26124.backend.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sih26124.backend.dto.EventCreateRequestDto;
import com.sih26124.backend.dto.EventResponseDto;
import com.sih26124.backend.dto.StatusUpdateRequestDto;
import com.sih26124.backend.model.EventLifecycleStatus;
import com.sih26124.backend.model.EventSeverity;
import com.sih26124.backend.service.TelemetryEventService;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(EventController.class)
public class EventControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private TelemetryEventService telemetryEventService;

    @Test
    public void testCreateEventSuccess() throws Exception {
        EventCreateRequestDto request = new EventCreateRequestDto();
        request.setBusId("BUS-TEST-101");
        request.setEventType("POTHOLE");
        request.setConfidence(0.92);
        request.setLatitude(18.5204);
        request.setLongitude(73.8567);
        request.setTimestamp("2026-09-07T22:00:00Z");

        EventResponseDto response = new EventResponseDto();
        response.setEventId("EVT-1234");
        response.setBusId("BUS-TEST-101");
        response.setEventType("POTHOLE");
        response.setConfidence(0.92);
        response.setSeverity(EventSeverity.HIGH);
        response.setLifecycleStatus(EventLifecycleStatus.DETECTED);

        Mockito.when(telemetryEventService.createEvent(any(EventCreateRequestDto.class))).thenReturn(response);

        mockMvc.perform(post("/api/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.eventId").value("EVT-1234"))
                .andExpect(jsonPath("$.eventType").value("POTHOLE"))
                .andExpect(jsonPath("$.lifecycleStatus").value("DETECTED"));
    }

    @Test
    public void testCreateEventValidationFailureInvalidConfidence() throws Exception {
        EventCreateRequestDto request = new EventCreateRequestDto();
        request.setBusId("BUS-101");
        request.setEventType("POTHOLE");
        request.setConfidence(1.5); // Invalid confidence > 1.0
        request.setTimestamp("2026-09-07T22:00:00Z");

        mockMvc.perform(post("/api/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400));
    }

    @Test
    public void testGetNearbyEvents() throws Exception {
        EventResponseDto response = new EventResponseDto();
        response.setEventId("EVT-NEARBY");
        response.setLatitude(18.5204);
        response.setLongitude(73.8567);

        Mockito.when(telemetryEventService.getNearbyEvents(eq(18.5204), eq(73.8567), eq(1000.0)))
                .thenReturn(List.of(response));

        mockMvc.perform(get("/api/events/nearby")
                        .param("latitude", "18.5204")
                        .param("longitude", "73.8567")
                        .param("radiusMeters", "1000.0"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].eventId").value("EVT-NEARBY"));
    }

    @Test
    public void testUpdateLifecycleStatus() throws Exception {
        StatusUpdateRequestDto request = new StatusUpdateRequestDto();
        request.setStatus(EventLifecycleStatus.VERIFIED);

        EventResponseDto response = new EventResponseDto();
        response.setEventId("EVT-1234");
        response.setLifecycleStatus(EventLifecycleStatus.VERIFIED);

        Mockito.when(telemetryEventService.updateLifecycleStatus(eq("EVT-1234"), eq(EventLifecycleStatus.VERIFIED)))
                .thenReturn(response);

        mockMvc.perform(patch("/api/events/EVT-1234/status")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.lifecycleStatus").value("VERIFIED"));
    }
}
