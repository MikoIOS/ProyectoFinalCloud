package com.example.backend_b.infrastructure.DTOs.request;

import com.example.backend_b.common.Enums.TipoAusencia;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;
import lombok.Data;

/** POST /api/v1/ausencias */
@Data
public class AusenciaRequest {
    @NotNull(message = "El tipo es obligatorio (VACACIONES, PERMISO, LICENCIA_MEDICA, SIN_GOCE)")
    private TipoAusencia tipo;

    @NotNull(message = "La fecha de inicio es obligatoria")
    private LocalDate desde;

    @NotNull(message = "La fecha de fin es obligatoria")
    private LocalDate hasta;

    @Size(max = 300, message = "El motivo admite como máximo 300 caracteres")
    private String motivo;

    /** Solo RR.HH.: registrar la solicitud a nombre de otro empleado. */
    private String empleadoId;
}
