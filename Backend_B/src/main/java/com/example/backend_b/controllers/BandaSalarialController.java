package com.example.backend_b.controllers;

import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.infrastructure.DTOs.Response.BandaSalarialResponse;
import com.example.backend_b.infrastructure.DTOs.request.BandaSalarialRequest;
import com.example.backend_b.services.BandaSalarialService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/** Bandas salariales por cargo. Lectura: admin_rrhh, gerente, reclutador. Escritura: admin_rrhh. */
@RestController
@RequestMapping("/api/v1/bandas")
public class BandaSalarialController {
    @Autowired private BandaSalarialService bandaService;

    @GetMapping
    public ResponseEntity<List<BandaSalarialResponse>> listar(@AuthenticationPrincipal AuthContext auth) {
        return ResponseEntity.ok(bandaService.listar(auth));
    }

    /** Crea o actualiza la banda del cargo indicado en el body. */
    @PutMapping
    public ResponseEntity<BandaSalarialResponse> guardar(@AuthenticationPrincipal AuthContext auth,
                                                         @Valid @RequestBody BandaSalarialRequest dto) {
        return ResponseEntity.ok(bandaService.guardar(auth, dto));
    }
}
