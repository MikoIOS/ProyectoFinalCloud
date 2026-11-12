package com.example.backend_b.controllers;

import com.example.backend_b.infrastructure.DTOs.request.EventoRequest;
import com.example.backend_b.services.EventoService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * Entrada de eventos de otros microservicios (EmpleadoCreado, EmpleadoActualizado, EmpleadoCesado…).
 * No usa JWT: si hcm.eventos.api-key está configurada, se exige la cabecera X-Api-Key.
 * Body: {"tipo_evento":"EmpleadoCreado","tenant_id":"andina","origen":"ms-empleados","timestamp":"…","datos":{…}}
 */
@RestController
@RequestMapping("/api/v1/eventos")
public class EventoController {
    @Autowired private EventoService eventoService;

    @PostMapping
    public ResponseEntity<Map<String, String>> recibir(@RequestHeader(value = "X-Api-Key", required = false) String apiKey,
                                                       @Valid @RequestBody EventoRequest evento) {
        String resultado = eventoService.recibir(evento, apiKey);
        return ResponseEntity.accepted().body(Map.of("tipo_evento", evento.getTipoEvento(), "resultado", resultado));
    }
}
