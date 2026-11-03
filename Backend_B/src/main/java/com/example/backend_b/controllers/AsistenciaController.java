package com.example.backend_b.controllers;

import com.example.backend_b.common.Enums.TipoReporte;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.infrastructure.DTOs.Response.ResumenAsistenciaResponse;
import com.example.backend_b.services.ReporteAsistenciaService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;

/** ms-asistencia: dashboard y reportes. */
@RestController
@RequestMapping("/api/v1/asistencia")
public class AsistenciaController {
    @Autowired private ReporteAsistenciaService reporteService;

    @GetMapping("/resumen")
    public ResponseEntity<ResumenAsistenciaResponse> resumen(@AuthenticationPrincipal AuthContext auth,
                                                             @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fecha) {
        return ResponseEntity.ok(reporteService.resumen(auth, fecha));
    }

    /** CSV del periodo: ?periodo=2026-10&tipo=MARCACIONES|AUSENCIAS */
    @GetMapping("/reportes")
    public ResponseEntity<byte[]> reporte(@AuthenticationPrincipal AuthContext auth,
                                          @RequestParam String periodo,
                                          @RequestParam(required = false) TipoReporte tipo) {
        ReporteAsistenciaService.Reporte r = reporteService.csv(auth, periodo, tipo);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("text/csv; charset=UTF-8"))
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + r.nombreArchivo() + "\"")
                .body(r.csv());
    }
}
