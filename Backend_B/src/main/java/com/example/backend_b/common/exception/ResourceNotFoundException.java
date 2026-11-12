package com.example.backend_b.common.exception;

/** Recurso no encontrado (404). */
public class ResourceNotFoundException extends RuntimeException {
    public ResourceNotFoundException(String message) {
        super(message);
    }
}
