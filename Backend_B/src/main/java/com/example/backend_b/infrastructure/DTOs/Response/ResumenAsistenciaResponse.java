package com.example.backend_b.infrastructure.DTOs.Response;

import java.time.LocalDate;

/** GET /api/v1/asistencia/resumen (dashboard). */
public record ResumenAsistenciaResponse(
        LocalDate fecha,
        long ausenciasPendientes,
        long marcacionesDelDia,
        long tardanzasDelDia) {
}
