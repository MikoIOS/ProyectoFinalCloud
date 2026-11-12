package com.example.backend_b.infrastructure.DTOs.Response;

import java.math.BigDecimal;
import java.time.LocalDate;

/** Marcaciones de un empleado en un rango, con totales. */
public record HistorialMarcacionesResponse(
        String empleadoId,
        LocalDate desde,
        LocalDate hasta,
        int diasMarcados,
        BigDecimal totalHoras,
        long tardanzas,
        PaginaResponse<MarcacionResponse> marcaciones) {
}
