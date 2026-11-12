package com.example.backend_b.controllers;

import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.infrastructure.DTOs.Response.HistorialMarcacionesResponse;
import com.example.backend_b.infrastructure.DTOs.Response.MarcacionResponse;
import com.example.backend_b.infrastructure.DTOs.Response.PaginaResponse;
import com.example.backend_b.infrastructure.DTOs.request.MarcacionRequest;
import com.example.backend_b.services.MarcacionService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;

/** ms-asistencia: marcaciones de entrada y salida. */
@RestController
@RequestMapping("/api/v1/marcaciones")
public class MarcacionController {
    @Autowired private MarcacionService marcacionService;

    /** Marca ENTRADA o SALIDA. Body opcional: {} basta para el autoservicio del empleado. */
    @PostMapping
    public ResponseEntity<MarcacionResponse> marcar(@AuthenticationPrincipal AuthContext auth,
                                                    @RequestBody(required = false) MarcacionRequest dto) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(marcacionService.marcar(auth, dto == null ? new MarcacionRequest() : dto));
    }

    /** Historial de un empleado (por defecto el propio y los últimos 31 días). */
    @GetMapping
    public ResponseEntity<HistorialMarcacionesResponse> historial(@AuthenticationPrincipal AuthContext auth,
                                                                  @RequestParam(required = false) String empleadoId,
                                                                  @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate desde,
                                                                  @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate hasta,
                                                                  @RequestParam(required = false) Integer page,
                                                                  @RequestParam(required = false) Integer size) {
        return ResponseEntity.ok(marcacionService.historial(auth, empleadoId, desde, hasta, page, size));
    }

    /** Todas las marcaciones de un día (admin_rrhh, gerente). */
    @GetMapping("/dia")
    public ResponseEntity<PaginaResponse<MarcacionResponse>> delDia(@AuthenticationPrincipal AuthContext auth,
                                                                    @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fecha,
                                                                    @RequestParam(required = false) Integer page,
                                                                    @RequestParam(required = false) Integer size) {
        return ResponseEntity.ok(marcacionService.delDia(auth, fecha, page, size));
    }
}
