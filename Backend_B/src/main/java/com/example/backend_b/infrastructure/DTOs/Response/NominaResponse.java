package com.example.backend_b.infrastructure.DTOs.Response;

import com.example.backend_b.common.Enums.EstadoNomina;
import com.example.backend_b.entities.Nomina;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

/** Nómina completa con su detalle (boleta). */
public record NominaResponse(
        Long id,
        String periodo,
        String empleadoId,
        String nombreEmpleado,
        String area,
        String cargo,
        BigDecimal salarioMensual,
        Integer diasLaborados,
        BigDecimal sueldoBase,
        BigDecimal bonos,
        BigDecimal descuentos,
        BigDecimal neto,
        BigDecimal aporteEssalud,
        EstadoNomina estado,
        String documento,
        Instant generadoEn,
        List<LineaNominaResponse> detalle) {

    public static NominaResponse de(Nomina n) {
        return new NominaResponse(n.getId(), n.getPeriodo(), n.getEmpleadoId(), n.getNombreEmpleado(), n.getArea(),
                n.getCargo(), n.getSalarioMensual(), n.getDiasLaborados(), n.getSueldoBase(), n.getBonos(), n.getDescuentos(),
                n.getNeto(), n.getAporteEssalud(), n.getEstado(), n.getDocumento(), n.getGeneradoEn(),
                n.getDetalle().stream().map(LineaNominaResponse::de).toList());
    }
}
