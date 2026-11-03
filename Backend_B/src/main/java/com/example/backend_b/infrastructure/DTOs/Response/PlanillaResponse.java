package com.example.backend_b.infrastructure.DTOs.Response;

import com.example.backend_b.common.Enums.EstadoPlanilla;
import com.example.backend_b.entities.Planilla;
import java.math.BigDecimal;
import java.time.Instant;

/** Cabecera de planilla: estado y totales. */
public record PlanillaResponse(
        Long id,
        String periodo,
        EstadoPlanilla estado,
        Integer totalEmpleados,
        Integer procesados,
        BigDecimal totalBruto,
        BigDecimal totalDescuentos,
        BigDecimal totalNeto,
        BigDecimal totalEssalud,
        Instant iniciadoEn,
        Instant completadoEn,
        String mensajeError) {

    public static PlanillaResponse de(Planilla p) {
        return new PlanillaResponse(p.getId(), p.getPeriodo(), p.getEstado(), p.getTotalEmpleados(), p.getProcesados(),
                p.getTotalBruto(), p.getTotalDescuentos(), p.getTotalNeto(), p.getTotalEssalud(),
                p.getIniciadoEn(), p.getCompletadoEn(), p.getMensajeError());
    }
}
