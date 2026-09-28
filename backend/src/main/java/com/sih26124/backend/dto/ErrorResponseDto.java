package com.sih26124.backend.dto;

import java.time.Instant;
import java.util.List;

public class ErrorResponseDto {

    private String timestamp = Instant.now().toString();
    private int status;
    private String error;
    private String message;
    private List<String> details;

    public ErrorResponseDto(int status, String error, String message, List<String> details) {
        this.status = status;
        this.error = error;
        this.message = message;
        this.details = details;
    }

    // Getters and Setters

    public String getTimestamp() {
        return timestamp;
    }

    public int getStatus() {
        return status;
    }

    public String getError() {
        return error;
    }

    public String getMessage() {
        return message;
    }

    public List<String> getDetails() {
        return details;
    }
}
