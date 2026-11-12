package com.example.backend_b.infrastructure.DTOs.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import java.util.HashMap;
import java.util.Map;
import lombok.Data;

/** Evento de otro microservicio, en el formato común del grupo: {tipo_evento, tenant_id, origen, timestamp, datos}. */
@Data
public class EventoRequest {
    @NotBlank(message = "tipo_evento es obligatorio")
    @JsonProperty("tipo_evento")
    private String tipoEvento;

    @NotBlank(message = "tenant_id es obligatorio")
    @JsonProperty("tenant_id")
    private String tenantId;

    private String origen;

    private String timestamp;

    private Map<String, Object> datos = new HashMap<>();
}
