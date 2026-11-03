package com.example.backend_b.infrastructure.DTOs.Response;

/** Solo desarrollo: JWT de prueba. */
public record TokenResponse(
        String token,
        String tenantId,
        String rol,
        String empleadoId) {
}
