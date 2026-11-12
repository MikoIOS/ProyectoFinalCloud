package com.example.backend_b.infrastructure.DTOs.Response;

import com.example.backend_b.entities.BandaSalarial;
import java.math.BigDecimal;
import java.math.RoundingMode;

/** Banda salarial por cargo. */
public record BandaSalarialResponse(
        Long id,
        String cargo,
        BigDecimal minimo,
        BigDecimal maximo,
        BigDecimal medio,
        String moneda) {

    public static BandaSalarialResponse de(BandaSalarial b) {
        BigDecimal medio = b.getMinimo().add(b.getMaximo()).divide(BigDecimal.valueOf(2), 2, RoundingMode.HALF_UP);
        return new BandaSalarialResponse(b.getId(), b.getCargo(), b.getMinimo(), b.getMaximo(), medio, b.getMoneda());
    }
}
