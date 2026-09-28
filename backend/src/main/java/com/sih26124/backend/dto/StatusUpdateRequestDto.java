package com.sih26124.backend.dto;

import com.sih26124.backend.model.EventLifecycleStatus;
import jakarta.validation.constraints.NotNull;

public class StatusUpdateRequestDto {

    @NotNull(message = "status is required")
    private EventLifecycleStatus status;

    public EventLifecycleStatus getStatus() {
        return status;
    }

    public void setStatus(EventLifecycleStatus status) {
        this.status = status;
    }
}
