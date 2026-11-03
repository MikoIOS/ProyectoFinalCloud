package com.example.backend_b.infrastructure.DTOs.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

/** POST /api/v1/nominas/generar */
@Data
public class GenerarPlanillaRequest {
    @NotBlank(message = "El periodo es obligatorio")
    @Pattern(regexp = "^\\d{4}-(0[1-9]|1[0-2])$", message = "El periodo debe tener el formato AAAA-MM")
    private String periodo;

    /** true para recalcular una planilla ya GENERADA (no aplica si está PAGADA). */
    private Boolean forzar;
}
