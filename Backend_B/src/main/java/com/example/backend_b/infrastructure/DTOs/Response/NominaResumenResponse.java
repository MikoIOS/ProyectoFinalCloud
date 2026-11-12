package com.example.backend_b.infrastructure.DTOs.Response;

import com.example.backend_b.common.Enums.EstadoNomina;
import com.example.backend_b.entities.Nomina;
import java.math.BigDecimal;

/** Nómina sin detalle (listados). */
public record NominaResumenResponse(
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
        EstadoNomina estado) {

    public static NominaResumenResponse de(Nomina n) {
        return new NominaResumenResponse(n.getId(), n.getPeriodo(), n.getEmpleadoId(), n.getNombreEmpleado(), n.getArea(),
                n.getCargo(), n.getSalarioMensual(), n.getDiasLaborados(), n.getSueldoBase(), n.getBonos(), n.getDescuentos(),
                n.getNeto(), n.getAporteEssalud(), n.getEstado());
    }
}
