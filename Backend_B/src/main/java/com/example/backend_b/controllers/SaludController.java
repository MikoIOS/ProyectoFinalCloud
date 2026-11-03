package com.example.backend_b.controllers;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** GET /api/v1/salud: health check público (balanceador, contenedor, etc.). */
@RestController
public class SaludController {

    @GetMapping("/api/v1/salud")
    public ResponseEntity<Map<String, Object>> salud() {
        return ResponseEntity.ok(Map.of("ok", true, "servicio", "Backend_B"));
    }
}
