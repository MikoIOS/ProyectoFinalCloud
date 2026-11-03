package com.example.backend_b.infrastructure.DTOs.request;

import com.example.backend_b.common.Enums.TipoConcepto;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import lombok.Data;

/** Bono o descuento manual para la planilla de un periodo. */
@Data
public class ConceptoNominaRequest {
    @NotBlank(message = "El empleado es obligatorio")
    private String empleadoId;

    @NotBlank(message = "El periodo es obligatorio")
    @Pattern(regexp = "^\\d{4}-(0[1-9]|1[0-2])$", message = "El periodo debe tener el formato AAAA-MM")
    private String periodo;

    /** BONO o DESCUENTO. */
    @NotNull(message = "El tipo es obligatorio (BONO o DESCUENTO)")
    private TipoConcepto tipo;

    @NotBlank(message = "El concepto es obligatorio")
    @Size(max = 80, message = "El concepto admite como máximo 80 caracteres")
    private String concepto;

    @NotNull(message = "El monto es obligatorio")
    @Positive(message = "El monto debe ser mayor a 0")
    @Digits(integer = 10, fraction = 2, message = "El monto admite como máximo 2 decimales")
    private BigDecimal monto;
}
