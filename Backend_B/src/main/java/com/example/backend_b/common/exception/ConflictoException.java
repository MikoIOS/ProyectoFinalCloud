package com.example.backend_b.common.exception;

/** El registro ya existe o cambió de estado (409). */
public class ConflictoException extends RuntimeException {
    public ConflictoException(String message) {
        super(message);
    }
}
