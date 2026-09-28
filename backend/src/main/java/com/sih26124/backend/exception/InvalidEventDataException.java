package com.sih26124.backend.exception;

public class InvalidEventDataException extends RuntimeException {
    public InvalidEventDataException(String message) {
        super(message);
    }
}
