package com.example.backend_b.controllers;

import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.infrastructure.DTOs.Response.LiquidacionResponse;
import com.example.backend_b.infrastructure.DTOs.Response.NominaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.NominaResumenResponse;
import com.example.backend_b.infrastructure.DTOs.Response.NominasEmpleadoResponse;
import com.example.backend_b.infrastructure.DTOs.Response.PaginaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.PlanillaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.ResumenNominasResponse;
import com.example.backend_b.infrastructure.DTOs.request.GenerarPlanillaRequest;
import com.example.backend_b.services.LiquidacionService;
import com.example.backend_b.services.NominaService;
import com.example.backend_b.services.PlanillaService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

/**
 * ms-nominas: planillas, boletas y liquidaciones.
 * Roles: generar = admin_rrhh; listados = admin_rrhh y gerente; boleta propia = el empleado.
 */
@RestController
@RequestMapping("/api/v1/nominas")
public class NominaController {
    @Autowired private PlanillaService planillaService;
    @Autowired private NominaService nominaService;
    @Autowired private LiquidacionService liquidacionService;

    /** Inicia la generación (asíncrona) de la planilla del periodo → 202. Consultar /planillas/{periodo}. */
    @PostMapping("/generar")
    public ResponseEntity<PlanillaResponse> generar(@AuthenticationPrincipal AuthContext auth,
                                                    @Valid @RequestBody GenerarPlanillaRequest dto) {
        return ResponseEntity.accepted().body(planillaService.generar(auth, dto));
    }

    @GetMapping
    public ResponseEntity<PaginaResponse<NominaResumenResponse>> listar(@AuthenticationPrincipal AuthContext auth,
                                                                        @RequestParam String periodo,
                                                                        @RequestParam(required = false) String area,
                                                                        @RequestParam(required = false) Integer page,
                                                                        @RequestParam(required = false) Integer size) {
        return ResponseEntity.ok(nominaService.listarPeriodo(auth, periodo, area, page, size));
    }

    /** Dashboard: totales de la planilla (la del periodo o la más reciente). */
    @GetMapping("/resumen")
    public ResponseEntity<ResumenNominasResponse> resumen(@AuthenticationPrincipal AuthContext auth,
                                                          @RequestParam(required = false) String periodo) {
        return ResponseEntity.ok(planillaService.resumen(auth, periodo));
    }

    @GetMapping("/planillas")
    public ResponseEntity<PaginaResponse<PlanillaResponse>> planillas(@AuthenticationPrincipal AuthContext auth,
                                                                      @RequestParam(required = false) Integer page,
                                                                      @RequestParam(required = false) Integer size) {
        return ResponseEntity.ok(planillaService.listar(auth, page, size));
    }

    @GetMapping("/planillas/{periodo}")
    public ResponseEntity<PlanillaResponse> planilla(@AuthenticationPrincipal AuthContext auth, @PathVariable String periodo) {
        return ResponseEntity.ok(planillaService.obtener(auth, periodo));
    }

    @GetMapping("/empleado/{empleadoId}")
    public ResponseEntity<NominasEmpleadoResponse> delEmpleado(@AuthenticationPrincipal AuthContext auth,
                                                               @PathVariable String empleadoId,
                                                               @RequestParam(required = false) Integer page,
                                                               @RequestParam(required = false) Integer size) {
        return ResponseEntity.ok(nominaService.delEmpleado(auth, empleadoId, page, size));
    }

    @GetMapping("/liquidaciones/{empleadoId}")
    public ResponseEntity<LiquidacionResponse> liquidacion(@AuthenticationPrincipal AuthContext auth, @PathVariable String empleadoId) {
        return ResponseEntity.ok(liquidacionService.obtener(auth, empleadoId));
    }

    @GetMapping("/{id}")
    public ResponseEntity<NominaResponse> obtener(@AuthenticationPrincipal AuthContext auth, @PathVariable Long id) {
        return ResponseEntity.ok(nominaService.detalle(auth, id));
    }

    /** Boleta en PDF. ?descargar=true la envía como adjunto. */
    @GetMapping("/{id}/boleta")
    public ResponseEntity<byte[]> boleta(@AuthenticationPrincipal AuthContext auth, @PathVariable Long id,
                                         @RequestParam(required = false, defaultValue = "false") boolean descargar) {
        NominaService.Boleta b = nominaService.boleta(auth, id);
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_PDF)
                .header(HttpHeaders.CONTENT_DISPOSITION, (descargar ? "attachment" : "inline") + "; filename=\"" + b.nombreArchivo() + "\"")
                .body(b.pdf());
    }
}
