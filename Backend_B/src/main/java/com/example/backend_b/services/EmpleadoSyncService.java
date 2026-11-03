package com.example.backend_b.services;

import com.example.backend_b.common.Enums.EstadoAusencia;
import com.example.backend_b.common.Enums.EstadoEmpleado;
import com.example.backend_b.entities.Ausencia;
import com.example.backend_b.entities.Empleado;
import com.example.backend_b.infrastructure.repositories.AusenciaRepository;
import com.example.backend_b.infrastructure.repositories.EmpleadoRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.Locale;
import java.util.Map;

/**
 * Mantiene la copia local de empleados a partir de los eventos de ms-empleados:
 * <ul>
 *   <li>EmpleadoCreado / EmpleadoActualizado → crea o actualiza (lo incluye en la planilla; saldo inicial de vacaciones)</li>
 *   <li>EmpleadoCesado → estado CESADO, liquidación y cancelación de sus ausencias pendientes</li>
 * </ul>
 * Es idempotente: recibir el mismo evento dos veces deja el mismo resultado.
 */
@Service
public class EmpleadoSyncService {

    private static final Logger log = LoggerFactory.getLogger(EmpleadoSyncService.class);

    private final EmpleadoRepository empleadoRepo;
    private final AusenciaRepository ausenciaRepo;
    private final LiquidacionService liquidacionService;
    private final Clock clock;
    private final ZoneId zona;
    private final int diasVacacionesAnuales;

    public EmpleadoSyncService(EmpleadoRepository empleadoRepo, AusenciaRepository ausenciaRepo,
                               LiquidacionService liquidacionService, Clock clock, ZoneId zona,
                               @Value("${hcm.asistencia.dias-vacaciones-anuales:30}") int diasVacacionesAnuales) {
        this.empleadoRepo = empleadoRepo;
        this.ausenciaRepo = ausenciaRepo;
        this.liquidacionService = liquidacionService;
        this.clock = clock;
        this.zona = zona;
        this.diasVacacionesAnuales = diasVacacionesAnuales;
    }

    @Transactional
    public Empleado crearOActualizar(String tenantId, Map<String, Object> datos, boolean esAlta) {
        String empleadoId = requerido(datos, "empleado_id");
        Empleado e = empleadoRepo.findByTenantIdAndEmpleadoId(tenantId, empleadoId).orElse(null);
        boolean nuevo = e == null;
        if (nuevo) {
            e = new Empleado();
            e.setTenantId(tenantId);
            e.setEmpleadoId(empleadoId);
            e.setEstado(EstadoEmpleado.ACTIVO);
            e.setDiasVacacionesUsados(0);
        }
        if (texto(datos, "nombres") != null) e.setNombres(texto(datos, "nombres"));
        if (texto(datos, "apellidos") != null) e.setApellidos(texto(datos, "apellidos"));
        if (texto(datos, "nombre") != null && e.getNombres() == null) e.setNombres(texto(datos, "nombre"));
        if (texto(datos, "documento") != null) e.setDocumento(texto(datos, "documento"));
        if (texto(datos, "email") != null) e.setEmail(texto(datos, "email"));
        if (texto(datos, "area") != null) e.setArea(texto(datos, "area"));
        if (texto(datos, "cargo") != null) e.setCargo(texto(datos, "cargo"));
        if (datos.containsKey("jefe_id")) e.setJefeId(texto(datos, "jefe_id"));
        if (fecha(datos, "fecha_ingreso") != null) e.setFechaIngreso(fecha(datos, "fecha_ingreso"));
        if (fecha(datos, "fecha_cese") != null) e.setFechaCese(fecha(datos, "fecha_cese"));
        BigDecimal salario = decimal(datos, "salario_base");
        if (salario != null) e.setSalarioBase(salario);
        String estado = texto(datos, "estado");
        if (estado != null) {
            try {
                e.setEstado(EstadoEmpleado.valueOf(estado.toUpperCase(Locale.ROOT)));
            } catch (IllegalArgumentException ignorado) {
                log.warn("Estado de empleado desconocido '{}', se mantiene {}", estado, e.getEstado());
            }
        }
        if (e.getDiasVacacionesAsignados() == null) {
            BigDecimal dv = decimal(datos, "dias_vacaciones");
            e.setDiasVacacionesAsignados(dv != null ? dv.intValue() : diasVacacionesAnuales);
        }
        e.setActualizadoEn(clock.instant());
        if (e.getSalarioBase() == null) {
            log.warn("Empleado {}/{} sin salario_base: no entrará en la planilla hasta que llegue", tenantId, empleadoId);
        }
        log.info("Empleado {} {}/{}", nuevo ? "creado" : "actualizado", tenantId, empleadoId);
        return empleadoRepo.save(e);
    }

    @Transactional
    public Empleado cesar(String tenantId, Map<String, Object> datos) {
        String empleadoId = requerido(datos, "empleado_id");
        Empleado e = empleadoRepo.findByTenantIdAndEmpleadoId(tenantId, empleadoId).orElseGet(() -> {
            Empleado nuevo = new Empleado();
            nuevo.setTenantId(tenantId);
            nuevo.setEmpleadoId(empleadoId);
            nuevo.setDiasVacacionesAsignados(diasVacacionesAnuales);
            nuevo.setDiasVacacionesUsados(0);
            return nuevo;
        });
        LocalDate cese = fecha(datos, "fecha_cese");
        if (cese == null) cese = LocalDate.now(clock.withZone(zona));
        e.setEstado(EstadoEmpleado.CESADO);
        e.setFechaCese(cese);
        e.setActualizadoEn(clock.instant());
        e = empleadoRepo.save(e);

        liquidacionService.registrar(e, cese, texto(datos, "motivo"));

        int canceladas = 0;
        for (Ausencia a : ausenciaRepo.findByTenantIdAndEmpleadoIdAndEstado(tenantId, empleadoId, EstadoAusencia.PENDIENTE)) {
            a.setEstado(EstadoAusencia.CANCELADA);
            a.setComentario("Cancelada por cese del empleado");
            a.setResueltoEn(clock.instant());
            canceladas++;
        }
        log.info("Empleado cesado {}/{} (ausencias pendientes canceladas: {})", tenantId, empleadoId, canceladas);
        return e;
    }

    // ------------------------------------------------------------ lectura de "datos"

    static String requerido(Map<String, Object> datos, String k) {
        String v = texto(datos, k);
        if (v == null) throw new IllegalArgumentException("El evento no trae datos." + k);
        return v;
    }

    static String texto(Map<String, Object> datos, String k) {
        Object v = datos == null ? null : datos.get(k);
        if (v == null) return null;
        String s = v.toString().trim();
        return s.isEmpty() ? null : s;
    }

    static BigDecimal decimal(Map<String, Object> datos, String k) {
        String s = texto(datos, k);
        if (s == null) return null;
        try {
            return new BigDecimal(s);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("datos." + k + " debe ser numérico");
        }
    }

    static LocalDate fecha(Map<String, Object> datos, String k) {
        String s = texto(datos, k);
        if (s == null) return null;
        try {
            return LocalDate.parse(s.length() > 10 ? s.substring(0, 10) : s);
        } catch (DateTimeParseException e) {
            throw new IllegalArgumentException("datos." + k + " debe tener formato AAAA-MM-DD");
        }
    }
}
