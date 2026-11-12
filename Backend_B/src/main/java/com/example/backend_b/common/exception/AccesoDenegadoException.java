package com.example.backend_b.common.exception;

/** El rol o el usuario no puede realizar la acción (403). */
public class AccesoDenegadoException extends RuntimeException {
    public AccesoDenegadoException(String message) {
        super(message);
    }
}
