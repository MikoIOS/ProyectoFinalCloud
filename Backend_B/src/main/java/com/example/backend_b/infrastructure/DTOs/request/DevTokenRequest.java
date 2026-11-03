package com.example.backend_b.infrastructure.DTOs.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/** Solo desarrollo: datos para emitir un JWT de prueba. */
@Data
public class DevTokenRequest {
    @NotBlank(message = "tenantId es obligatorio")
    private String tenantId;

    @NotBlank(message = "rol es obligatorio")
    private String rol;

    private String empleadoId;

    private String userId;
}
