package com.example.backend_b.infrastructure.DTOs.Response;

import com.example.backend_b.common.Enums.TipoLineaNomina;
import com.example.backend_b.entities.NominaDetalle;
import java.math.BigDecimal;

/** Línea de la boleta. */
public record LineaNominaResponse(
        TipoLineaNomina tipo,
        String concepto,
        BigDecimal monto) {

    public static LineaNominaResponse de(NominaDetalle d) {
        return new LineaNominaResponse(d.getTipo(), d.getConcepto(), d.getMonto());
    }
}
