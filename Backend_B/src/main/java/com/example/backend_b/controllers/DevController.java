package com.example.backend_b.controllers;

import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.common.security.JwtService;
import com.example.backend_b.infrastructure.DTOs.Response.TokenResponse;
import com.example.backend_b.infrastructure.DTOs.request.DevTokenRequest;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * SOLO DESARROLLO (hcm.dev.habilitado=true): emite JWT de prueba con el mismo secreto que se valida,
 * para probar sin ms-usuarios. En producción no existe esta ruta.
 */
@RestController
@RequestMapping("/api/v1")
@ConditionalOnProperty(name = "hcm.dev.habilitado", havingValue = "true")
public class DevController {
    @Autowired private JwtService jwtService;

    @PostMapping("/dev/token")
    public ResponseEntity<TokenResponse> token(@Valid @RequestBody DevTokenRequest dto) {
        String userId = dto.getUserId() != null ? dto.getUserId() : "usr-dev-" + dto.getRol();
        AuthContext ctx = new AuthContext(dto.getTenantId(), userId, dto.getRol(), dto.getEmpleadoId());
        return ResponseEntity.ok(new TokenResponse(jwtService.emitir(ctx, 12 * 3600), ctx.tenantId(), ctx.rol(), ctx.empleadoId()));
    }
}
