package com.example.backend_b.infrastructure.DTOs.Response;

import com.example.backend_b.entities.Liquidacion;
import java.math.BigDecimal;
import java.time.LocalDate;

/** Liquidación por cese. */
public record LiquidacionResponse(
        String empleadoId,
        LocalDate fechaCese,
        String motivo,
        BigDecimal vacacionesTruncas,
        BigDecimal ctsTrunca,
        BigDecimal gratificacionTrunca,
        BigDecimal total) {

    public static LiquidacionResponse de(Liquidacion l) {
        return new LiquidacionResponse(l.getEmpleadoId(), l.getFechaCese(), l.getMotivo(), l.getVacacionesTruncas(),
                l.getCtsTrunca(), l.getGratificacionTrunca(), l.getTotal());
    }
}
