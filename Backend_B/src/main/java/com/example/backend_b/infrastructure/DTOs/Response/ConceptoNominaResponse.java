package com.example.backend_b.infrastructure.DTOs.Response;

import com.example.backend_b.common.Enums.OrigenConcepto;
import com.example.backend_b.common.Enums.TipoConcepto;
import com.example.backend_b.entities.ConceptoNomina;
import java.math.BigDecimal;

/** Bono / descuento / días sin goce. */
public record ConceptoNominaResponse(
        Long id,
        String empleadoId,
        String periodo,
        TipoConcepto tipo,
        String concepto,
        BigDecimal monto,
        Integer dias,
        OrigenConcepto origen,
        String referencia) {

    public static ConceptoNominaResponse de(ConceptoNomina c) {
        return new ConceptoNominaResponse(c.getId(), c.getEmpleadoId(), c.getPeriodo(), c.getTipo(), c.getConcepto(),
                c.getMonto(), c.getDias(), c.getOrigen(), c.getReferencia());
    }
}
