package com.example.backend_b.infrastructure.DTOs.Response;

import com.example.backend_b.common.Enums.EstadoAusencia;
import com.example.backend_b.common.Enums.TipoAusencia;
import com.example.backend_b.entities.Ausencia;
import java.time.Instant;
import java.time.LocalDate;

/** Solicitud de ausencia. */
public record AusenciaResponse(
        Long id,
        String empleadoId,
        String nombreEmpleado,
        TipoAusencia tipo,
        Boolean conGoce,
        LocalDate desde,
        LocalDate hasta,
        Integer dias,
        String motivo,
        EstadoAusencia estado,
        String aprobadorId,
        Instant solicitadoEn,
        String resueltoPorEmpleado,
        Instant resueltoEn,
        String comentario) {

    public static AusenciaResponse de(Ausencia a) {
        return new AusenciaResponse(a.getId(), a.getEmpleadoId(), a.getNombreEmpleado(), a.getTipo(), a.getConGoce(),
                a.getDesde(), a.getHasta(), a.getDias(), a.getMotivo(), a.getEstado(), a.getAprobadorId(), a.getSolicitadoEn(),
                a.getResueltoPorEmpleado(), a.getResueltoEn(), a.getComentario());
    }
}
