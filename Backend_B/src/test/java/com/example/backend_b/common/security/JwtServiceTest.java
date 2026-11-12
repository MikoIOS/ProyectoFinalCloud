package com.example.backend_b.common.security;

import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class JwtServiceTest {

    private final JwtService jwt = new JwtService("secreto-de-prueba");

    @Test
    void emiteYValida() {
        String token = jwt.emitir(new AuthContext("andina", "usr-1", "admin_rrhh", "emp-000002"), 60);
        AuthContext a = jwt.validar(token);
        assertEquals("andina", a.tenantId());
        assertEquals("usr-1", a.userId());
        assertEquals("admin_rrhh", a.rol());
        assertEquals("emp-000002", a.empleadoId());
    }

    @Test
    void rechazaFirmaAjenaExpiradoYMalFormado() {
        String ajeno = new JwtService("otro").emitir(new AuthContext("andina", "u", "empleado", null), 60);
        assertThrows(IllegalArgumentException.class, () -> jwt.validar(ajeno));
        String expirado = jwt.emitir(new AuthContext("andina", "u", "empleado", null), -10);
        assertThrows(IllegalArgumentException.class, () -> jwt.validar(expirado));
        assertThrows(IllegalArgumentException.class, () -> jwt.validar("a.b"));
        assertThrows(IllegalArgumentException.class, () -> jwt.validar("no-es-un-token"));
    }

    @Test
    void aceptaClaimsDeOtrosFormatos() {
        // p.ej. un token de ms-usuarios con "sub", "role", claims anidados y valores con escapes
        String json = "{\"sub\":\"usr-9\",\"custom:tenant_id\":\"pacifico\",\"role\":\"gerente\",\"permisos\":[\"a\",\"b\"],"
                + "\"perfil\":{\"x\":1},\"nombre\":\"Jos\\u00e9 \\\"Pepe\\\"\",\"exp\":" + (Instant.now().getEpochSecond() + 60) + "}";
        var claims = MiniJson.parse(json);
        assertEquals("José \"Pepe\"", claims.get("nombre"));
        assertEquals("[\"a\",\"b\"]", claims.get("permisos"));
        assertEquals("pacifico", claims.get("custom:tenant_id"));
    }

    @Test
    void roles() {
        AuthContext emp = new AuthContext("andina", "u", AuthContext.EMPLEADO, "emp-1");
        assertThrows(RuntimeException.class, () -> emp.exigirRol(AuthContext.ADMIN_RRHH));
        assertThrows(RuntimeException.class, () -> emp.exigirPropioOSupervisor("emp-2", "no"));
        emp.exigirPropioOSupervisor("emp-1", "no");
        new AuthContext("andina", "u", AuthContext.GERENTE, null).exigirPropioOSupervisor("emp-2", "no");
    }
}
