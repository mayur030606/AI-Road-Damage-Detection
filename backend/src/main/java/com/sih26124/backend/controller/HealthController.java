package com.sih26124.backend.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {

    @GetMapping("/")
    public String home() {
        return "FleetVision Backend is running";
    }

    @GetMapping("/api/health")
    public String health() {
        return "FleetVision Backend is healthy";
    }
}