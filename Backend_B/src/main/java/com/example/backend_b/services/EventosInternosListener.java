package com.example.backend_b.services;

import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.time.LocalDate;

/**
 * Reacciones de nóminas a los eventos que publica asistencia dentro de la misma app
 * (en el diseño EDA del grupo esto sería la cola SQS de ms-nominas):
 * AusenciaAprobada sin goce → días a descontar en la planilla.
 * Corre en la misma transacción que la aprobación: si algo falla, no se aprueba.
 */
@Component
public class EventosInternosListener {

    private final ConceptoNominaService conceptos;

    public EventosInternosListener(ConceptoNominaService conceptos) {
        this.conceptos = conceptos;
    }

    @EventListener
    public void alPublicar(EventoPublisher.EventoDominio e) {
        if ("AusenciaAprobada".equals(e.tipoEvento()) && Boolean.FALSE.equals(e.datos().get("con_goce"))) {
            conceptos.registrarSinGoce(e.tenantId(),
                    String.valueOf(e.datos().get("empleado_id")),
                    String.valueOf(e.datos().get("ausencia_id")),
                    fecha(e.datos().get("desde")),
                    fecha(e.datos().get("hasta")));
        }
    }

    static LocalDate fecha(Object v) {
        if (v instanceof LocalDate d) return d;
        if (v == null) throw new IllegalArgumentException("Falta la fecha en el evento");
        return LocalDate.parse(v.toString().substring(0, 10));
    }
}
