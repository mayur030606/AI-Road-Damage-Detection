package com.sih26124.backend.controller;

import com.sih26124.backend.dto.EventCreateRequestDto;
import com.sih26124.backend.dto.EventResponseDto;
import com.sih26124.backend.dto.StatusUpdateRequestDto;
import com.sih26124.backend.service.TelemetryEventService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/events")
@CrossOrigin(origins = {"http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"})
public class EventController {

    private final TelemetryEventService service;

    public EventController(TelemetryEventService service) {
        this.service = service;
    }

    @PostMapping
    public ResponseEntity<EventResponseDto> createEvent(@Valid @RequestBody EventCreateRequestDto requestDto) {
        EventResponseDto created = service.createEvent(requestDto);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @GetMapping
    public ResponseEntity<List<EventResponseDto>> getAllEvents(
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String severity
    ) {
        List<EventResponseDto> events = service.getAllEvents(type, status, severity);
        return ResponseEntity.ok(events);
    }

    @GetMapping("/{id}")
    public ResponseEntity<EventResponseDto> getEventById(@PathVariable String id) {
        EventResponseDto event = service.getEventById(id);
        return ResponseEntity.ok(event);
    }

    @GetMapping("/nearby")
    public ResponseEntity<List<EventResponseDto>> getNearbyEvents(
            @RequestParam double latitude,
            @RequestParam double longitude,
            @RequestParam(defaultValue = "1000.0") double radiusMeters
    ) {
        List<EventResponseDto> events = service.getNearbyEvents(latitude, longitude, radiusMeters);
        return ResponseEntity.ok(events);
    }

    @PatchMapping("/{id}/status")
    public ResponseEntity<EventResponseDto> updateStatus(
            @PathVariable String id,
            @Valid @RequestBody StatusUpdateRequestDto requestDto
    ) {
        EventResponseDto updated = service.updateLifecycleStatus(id, requestDto.getStatus());
        return ResponseEntity.ok(updated);
    }
}
