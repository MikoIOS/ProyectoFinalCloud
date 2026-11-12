package com.example.backend_b.common.exception;

/** La operación viola una regla de negocio: saldo insuficiente, planilla pagada, etc. (422). */
public class ReglaNegocioException extends RuntimeException {
    public ReglaNegocioException(String message) {
        super(message);
    }
}
