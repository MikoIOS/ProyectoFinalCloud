package com.example.backend_b.common.security;

import com.example.backend_b.common.exception.AccesoDenegadoException;

import java.util.Arrays;

/**
 * Identidad del llamante, tomada del JWT que emite ms-usuarios (claims tenant_id, user_id, rol, empleado_id).
 * Se recibe en los controllers con {@code @AuthenticationPrincipal AuthContext auth}.
 * El tenant SIEMPRE sale de aquí, nunca del body ni de la URL.
 */
public record AuthContext(String tenantId, String userId, String rol, String empleadoId) {

    public static final String ADMIN_RRHH = "admin_rrhh";
    public static final String GERENTE = "gerente";
    public static final String RECLUTADOR = "reclutador";
    public static final String EMPLEADO = "empleado";

    public boolean tieneRol(String... roles) {
        return rol != null && Arrays.asList(roles).contains(rol);
    }

    public boolean esAdmin() {
        return ADMIN_RRHH.equals(rol);
    }

    /** admin_rrhh o gerente: pueden ver la información de todos los empleados del tenant. */
    public boolean esSupervisor() {
        return tieneRol(ADMIN_RRHH, GERENTE);
    }

    public void exigirRol(String... roles) {
        if (!tieneRol(roles)) {
            throw new AccesoDenegadoException("El rol '" + rol + "' no puede realizar esta acción");
        }
    }

    public boolean esElEmpleado(String empleadoIdObjetivo) {
        return empleadoId != null && empleadoId.equals(empleadoIdObjetivo);
    }

    /** Supervisor o el propio empleado (autoservicio). */
    public void exigirPropioOSupervisor(String empleadoIdObjetivo, String mensaje) {
        if (!esSupervisor() && !esElEmpleado(empleadoIdObjetivo)) {
            throw new AccesoDenegadoException(mensaje);
        }
    }

    public String exigirEmpleadoPropio() {
        if (empleadoId == null || empleadoId.isBlank()) {
            throw new AccesoDenegadoException("Tu usuario no está vinculado a un empleado (falta empleado_id en el token)");
        }
        return empleadoId;
    }
}
