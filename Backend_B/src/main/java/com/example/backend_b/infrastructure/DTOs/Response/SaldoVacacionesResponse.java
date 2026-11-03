package com.example.backend_b.infrastructure.DTOs.Response;

/** Saldo de vacaciones. */
public record SaldoVacacionesResponse(
        String empleadoId,
        int diasAsignados,
        int diasUsados,
        int diasPendientesAprobacion,
        int diasDisponibles) {
}
