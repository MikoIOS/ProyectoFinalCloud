package com.example.backend_b.controllers;

import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.infrastructure.DTOs.Response.ConceptoNominaResponse;
import com.example.backend_b.infrastructure.DTOs.request.ConceptoNominaRequest;
import com.example.backend_b.services.ConceptoNominaService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/** Bonos y descuentos manuales de la planilla (los días sin goce llegan solos desde asistencia). */
@RestController
@RequestMapping("/api/v1/nominas/conceptos")
public class ConceptoNominaController {
    @Autowired private ConceptoNominaService conceptoService;

    @PostMapping
    public ResponseEntity<ConceptoNominaResponse> crear(@AuthenticationPrincipal AuthContext auth,
                                                        @Valid @RequestBody ConceptoNominaRequest dto) {
        return ResponseEntity.status(HttpStatus.CREATED).body(conceptoService.crear(auth, dto));
    }

    @GetMapping
    public ResponseEntity<List<ConceptoNominaResponse>> listar(@AuthenticationPrincipal AuthContext auth,
                                                               @RequestParam String periodo,
                                                               @RequestParam(required = false) String empleadoId) {
        return ResponseEntity.ok(conceptoService.listar(auth, periodo, empleadoId));
    }
}
