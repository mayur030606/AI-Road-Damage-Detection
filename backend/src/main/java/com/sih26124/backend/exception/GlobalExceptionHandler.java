package com.sih26124.backend.exception;

import com.sih26124.backend.dto.ErrorResponseDto;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.List;
import java.util.stream.Collectors;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponseDto> handleValidationErrors(MethodArgumentNotValidException ex) {
        List<String> details = ex.getBindingResult().getFieldErrors().stream()
                .map(err -> err.getField() + ": " + err.getDefaultMessage())
                .collect(Collectors.toList());

        ErrorResponseDto error = new ErrorResponseDto(
                HttpStatus.BAD_REQUEST.value(),
                "Bad Request",
                "Validation failed for incoming telemetry event",
                details
        );
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(error);
    }

    @ExceptionHandler(InvalidEventDataException.class)
    public ResponseEntity<ErrorResponseDto> handleInvalidEventData(InvalidEventDataException ex) {
        ErrorResponseDto error = new ErrorResponseDto(
                HttpStatus.BAD_REQUEST.value(),
                "Bad Request",
                ex.getMessage(),
                List.of(ex.getMessage())
        );
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(error);
    }

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponseDto> handleNotFound(ResourceNotFoundException ex) {
        ErrorResponseDto error = new ErrorResponseDto(
                HttpStatus.NOT_FOUND.value(),
                "Not Found",
                ex.getMessage(),
                List.of(ex.getMessage())
        );
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponseDto> handleGenericException(Exception ex) {
        ErrorResponseDto error = new ErrorResponseDto(
                HttpStatus.INTERNAL_SERVER_ERROR.value(),
                "Internal Server Error",
                "An unexpected error occurred",
                List.of(ex.getMessage() != null ? ex.getMessage() : "Unknown error")
        );
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
    }
}
