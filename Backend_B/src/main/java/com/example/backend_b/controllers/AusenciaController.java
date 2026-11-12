package com.example.backend_b.controllers;

import com.example.backend_b.common.Enums.EstadoAusencia;
import com.example.backend_b.common.Enums.TipoAusencia;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.infrastructure.DTOs.Response.AusenciaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.PaginaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.SaldoVacacionesResponse;
import com.example.backend_b.infrastructure.DTOs.request.AusenciaRequest;
import com.example.backend_b.infrastructure.DTOs.request.CambiarEstadoAusenciaRequest;
import com.example.backend_b.services.AusenciaService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

/** ms-asistencia: vacaciones, permisos, licencias y ausencias sin goce, con aprobación del jefe. */
@RestController
@RequestMapping("/api/v1/ausencias")
public class AusenciaController {
    @Autowired private AusenciaService ausenciaService;

    @PostMapping
    public ResponseEntity<AusenciaResponse> solicitar(@AuthenticationPrincipal AuthContext auth,
                                                      @Valid @RequestBody AusenciaRequest dto) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ausenciaService.solicitar(auth, dto));
    }

    @GetMapping
    public ResponseEntity<PaginaResponse<AusenciaResponse>> listar(@AuthenticationPrincipal AuthContext auth,
                                                                   @RequestParam(required = false) String empleadoId,
                                                                   @RequestParam(required = false) EstadoAusencia estado,
                                                                   @RequestParam(required = false) TipoAusencia tipo,
                                                                   @RequestParam(required = false) Integer page,
                                                                   @RequestParam(required = false) Integer size) {
        return ResponseEntity.ok(ausenciaService.listar(auth, empleadoId, estado, tipo, page, size));
    }

    /** Bandeja de aprobación del jefe. admin_rrhh: bandeja de RR.HH. o ?todas=true. */
    @GetMapping("/pendientes")
    public ResponseEntity<PaginaResponse<AusenciaResponse>> pendientes(@AuthenticationPrincipal AuthContext auth,
                                                                       @RequestParam(required = false, defaultValue = "false") boolean todas,
                                                                       @RequestParam(required = false) Integer page,
                                                                       @RequestParam(required = false) Integer size) {
        return ResponseEntity.ok(ausenciaService.pendientes(auth, todas, page, size));
    }

    @GetMapping("/saldo/{empleadoId}")
    public ResponseEntity<SaldoVacacionesResponse> saldo(@AuthenticationPrincipal AuthContext auth, @PathVariable String empleadoId) {
        return ResponseEntity.ok(ausenciaService.saldo(auth, empleadoId));
    }

    @GetMapping("/{id}")
    public ResponseEntity<AusenciaResponse> obtener(@AuthenticationPrincipal AuthContext auth, @PathVariable Long id) {
        return ResponseEntity.ok(ausenciaService.obtener(auth, id));
    }

    /** {estado: APROBADA | RECHAZADA | CANCELADA, comentario} */
    @PatchMapping("/{id}/estado")
    public ResponseEntity<AusenciaResponse> cambiarEstado(@AuthenticationPrincipal AuthContext auth, @PathVariable Long id,
                                                          @Valid @RequestBody CambiarEstadoAusenciaRequest dto) {
        return ResponseEntity.ok(ausenciaService.cambiarEstado(auth, id, dto));
    }
}
