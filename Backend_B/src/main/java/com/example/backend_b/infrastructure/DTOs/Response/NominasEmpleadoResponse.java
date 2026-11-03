package com.example.backend_b.infrastructure.DTOs.Response;

import java.util.List;

/** Historial de boletas de un empleado (+ liquidación si cesó). */
public record NominasEmpleadoResponse(
        String empleadoId,
        PaginaResponse<NominaResumenResponse> nominas,
        LiquidacionResponse liquidacion) {
}
