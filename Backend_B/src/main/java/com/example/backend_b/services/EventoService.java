package com.example.backend_b.services;

import com.example.backend_b.common.exception.AccesoDenegadoException;
import com.example.backend_b.infrastructure.DTOs.request.EventoRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.util.Map;

/**
 * Entrada de eventos de otros microservicios (POST /api/v1/eventos). Al desplegar se conecta aquí
 * la suscripción del topic/cola del grupo. Eventos que procesa:
 * <ul>
 *   <li>EmpleadoCreado / EmpleadoActualizado / EmpleadoCesado (de ms-empleados)</li>
 *   <li>AusenciaAprobada sin goce (si llegara desde afuera)</li>
 * </ul>
 * Los demás tipos se ignoran (responde "ignorado").
 */
@Service
public class EventoService {

    private static final Logger log = LoggerFactory.getLogger(EventoService.class);

    private final EmpleadoSyncService empleados;
    private final ConceptoNominaService conceptos;
    private final String apiKey;

    public EventoService(EmpleadoSyncService empleados, ConceptoNominaService conceptos,
                         @Value("${hcm.eventos.api-key:}") String apiKey) {
        this.empleados = empleados;
        this.conceptos = conceptos;
        this.apiKey = apiKey == null ? "" : apiKey.trim();
    }

    /** @return "procesado" o "ignorado" */
    public String recibir(EventoRequest e, String apiKeyRecibida) {
        if (!apiKey.isEmpty() && (apiKeyRecibida == null || !MessageDigest.isEqual(
                apiKey.getBytes(StandardCharsets.UTF_8), apiKeyRecibida.trim().getBytes(StandardCharsets.UTF_8)))) {
            throw new AccesoDenegadoException("X-Api-Key inválida");
        }
        Map<String, Object> datos = e.getDatos() == null ? Map.of() : e.getDatos();
        String tenant = e.getTenantId().trim();
        switch (e.getTipoEvento()) {
            case "EmpleadoCreado" -> empleados.crearOActualizar(tenant, datos, true);
            case "EmpleadoActualizado" -> empleados.crearOActualizar(tenant, datos, false);
            case "EmpleadoCesado" -> empleados.cesar(tenant, datos);
            case "AusenciaAprobada" -> {
                if (!Boolean.FALSE.equals(datos.get("con_goce")) && !"SIN_GOCE".equals(String.valueOf(datos.get("tipo")))) {
                    return "ignorado";
                }
                conceptos.registrarSinGoce(tenant,
                        EmpleadoSyncService.requerido(datos, "empleado_id"),
                        EmpleadoSyncService.requerido(datos, "ausencia_id"),
                        fechaRequerida(datos, "desde"),
                        fechaRequerida(datos, "hasta"));
            }
            default -> {
                log.info("Evento {} no es para Backend B, se ignora", e.getTipoEvento());
                return "ignorado";
            }
        }
        return "procesado";
    }

    private static java.time.LocalDate fechaRequerida(Map<String, Object> datos, String k) {
        java.time.LocalDate f = EmpleadoSyncService.fecha(datos, k);
        if (f == null) throw new IllegalArgumentException("El evento no trae datos." + k);
        return f;
    }
}
