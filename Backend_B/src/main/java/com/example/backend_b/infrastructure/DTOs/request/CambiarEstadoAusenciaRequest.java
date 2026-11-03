package com.example.backend_b.infrastructure.DTOs.request;

import com.example.backend_b.common.Enums.EstadoAusencia;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

/** PATCH /api/v1/ausencias/{id}/estado */
@Data
public class CambiarEstadoAusenciaRequest {
    /** APROBADA, RECHAZADA o CANCELADA. */
    @NotNull(message = "El estado es obligatorio")
    private EstadoAusencia estado;

    @Size(max = 300, message = "El comentario admite como máximo 300 caracteres")
    private String comentario;
}
