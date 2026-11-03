package com.example.backend_b.infrastructure.DTOs.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import lombok.Data;

/** Crea o actualiza la banda salarial de un cargo. */
@Data
public class BandaSalarialRequest {
    @NotBlank(message = "El cargo es obligatorio")
    @Size(max = 80)
    private String cargo;

    @NotNull(message = "El mínimo es obligatorio")
    @Positive(message = "El mínimo debe ser mayor a 0")
    private BigDecimal minimo;

    @NotNull(message = "El máximo es obligatorio")
    @Positive(message = "El máximo debe ser mayor a 0")
    private BigDecimal maximo;

    @Size(min = 3, max = 3, message = "La moneda es un código de 3 letras (PEN, USD)")
    private String moneda;
}
