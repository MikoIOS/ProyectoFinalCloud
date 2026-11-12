package com.example.backend_b.infrastructure.DTOs.request;

import com.example.backend_b.common.Enums.TipoMarcacion;
import java.time.LocalDate;
import java.time.LocalTime;
import lombok.Data;

/** POST /api/v1/marcaciones. Todo es opcional: sin datos marca ENTRADA o SALIDA a la hora actual. empleadoId/fecha/hora solo para RR.HH. */
@Data
public class MarcacionRequest {
    private TipoMarcacion tipo;

    private String empleadoId;

    private LocalDate fecha;

    /** "HH:mm" */
    private LocalTime hora;
}
