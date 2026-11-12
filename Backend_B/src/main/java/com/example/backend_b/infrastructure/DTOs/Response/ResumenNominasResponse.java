package com.example.backend_b.infrastructure.DTOs.Response;

import com.example.backend_b.common.Enums.EstadoPlanilla;
import java.math.BigDecimal;

/** GET /api/v1/nominas/resumen (dashboard). */
public record ResumenNominasResponse(
        String periodo,
        EstadoPlanilla estadoPlanilla,
        Integer empleadosEnPlanilla,
        BigDecimal totalBruto,
        BigDecimal totalDescuentos,
        BigDecimal totalNeto,
        BigDecimal totalEssalud,
        long empleadosActivos) {
}
