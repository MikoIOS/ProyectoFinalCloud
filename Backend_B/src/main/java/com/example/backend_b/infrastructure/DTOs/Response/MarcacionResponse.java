package com.example.backend_b.infrastructure.DTOs.Response;

import com.example.backend_b.common.Enums.EstadoMarcacion;
import com.example.backend_b.entities.Marcacion;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalTime;

/** Marcación del día. */
public record MarcacionResponse(
        Long id,
        String empleadoId,
        LocalDate fecha,
        LocalTime horaEntrada,
        LocalTime horaSalida,
        BigDecimal horas,
        Integer tardanzaMinutos,
        Boolean tarde,
        EstadoMarcacion estado,
        String origen) {

    public static MarcacionResponse de(Marcacion m) {
        return new MarcacionResponse(m.getId(), m.getEmpleadoId(), m.getFecha(), m.getHoraEntrada(), m.getHoraSalida(),
                m.getHoras(), m.getTardanzaMinutos(), m.getTarde(), m.getEstado(), m.getOrigen());
    }
}
