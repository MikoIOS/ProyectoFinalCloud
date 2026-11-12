package com.example.backend_b.services;

import com.example.backend_b.common.Enums.EstadoEmpleado;
import com.example.backend_b.common.Enums.EstadoMarcacion;
import com.example.backend_b.common.Enums.TipoMarcacion;
import com.example.backend_b.common.Utils;
import com.example.backend_b.common.exception.AccesoDenegadoException;
import com.example.backend_b.common.exception.ConflictoException;
import com.example.backend_b.common.exception.ReglaNegocioException;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.entities.Empleado;
import com.example.backend_b.entities.Marcacion;
import com.example.backend_b.infrastructure.DTOs.Response.HistorialMarcacionesResponse;
import com.example.backend_b.infrastructure.DTOs.Response.MarcacionResponse;
import com.example.backend_b.infrastructure.DTOs.Response.PaginaResponse;
import com.example.backend_b.infrastructure.DTOs.request.MarcacionRequest;
import com.example.backend_b.infrastructure.repositories.EmpleadoRepository;
import com.example.backend_b.infrastructure.repositories.MarcacionRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Clock;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.List;

/** Marcaciones de entrada / salida: una por empleado y día, con cálculo de horas y tardanza. */
@Service
public class MarcacionService {

    private final MarcacionRepository repository;
    private final EmpleadoRepository empleadoRepo;
    private final Clock clock;
    private final ZoneId zona;
    private final LocalTime horaIngreso;
    private final int toleranciaMinutos;

    public MarcacionService(MarcacionRepository repository, EmpleadoRepository empleadoRepo, Clock clock, ZoneId zona,
                            @Value("${hcm.asistencia.hora-ingreso:09:00}") String horaIngreso,
                            @Value("${hcm.asistencia.tolerancia-minutos:10}") int toleranciaMinutos) {
        this.repository = repository;
        this.empleadoRepo = empleadoRepo;
        this.clock = clock;
        this.zona = zona;
        this.horaIngreso = LocalTime.parse(horaIngreso);
        this.toleranciaMinutos = toleranciaMinutos;
    }

    /**
     * El empleado marca con la hora del servidor (zona del negocio). RR.HH. puede registrar o corregir
     * la marcación de otro empleado indicando empleadoId, fecha y hora. Sin "tipo": si no hay entrada
     * hoy marca ENTRADA; si ya hay entrada, SALIDA.
     */
    @Transactional
    public MarcacionResponse marcar(AuthContext auth, MarcacionRequest dto) {
        boolean paraOtro = dto.getEmpleadoId() != null && !auth.esElEmpleado(dto.getEmpleadoId());
        String empleadoId;
        if (paraOtro) {
            auth.exigirRol(AuthContext.ADMIN_RRHH);
            empleadoId = dto.getEmpleadoId();
        } else {
            empleadoId = auth.exigirEmpleadoPropio();
        }
        ZonedDateTime ahora = ZonedDateTime.now(clock.withZone(zona));
        LocalDate fecha = ahora.toLocalDate();
        LocalTime hora = ahora.toLocalTime().withSecond(0).withNano(0);
        if (paraOtro || auth.esAdmin()) {
            if (dto.getFecha() != null) fecha = dto.getFecha();
            if (dto.getHora() != null) hora = dto.getHora().withSecond(0).withNano(0);
        } else if (dto.getFecha() != null || dto.getHora() != null) {
            throw new AccesoDenegadoException("Solo RR.HH. puede registrar marcaciones con fecha u hora manual");
        }
        if (fecha.isAfter(ahora.toLocalDate())) throw new IllegalArgumentException("No se puede marcar en una fecha futura");

        Empleado empleado = empleadoRepo.findByTenantIdAndEmpleadoId(auth.tenantId(), empleadoId).orElse(null);
        if (empleado != null && empleado.getEstado() == EstadoEmpleado.CESADO) {
            throw new ReglaNegocioException("El empleado " + empleadoId + " está cesado");
        }

        Marcacion actual = repository.findByTenantIdAndEmpleadoIdAndFecha(auth.tenantId(), empleadoId, fecha).orElse(null);
        TipoMarcacion tipo = dto.getTipo();
        if (tipo == null) {
            if (actual == null) tipo = TipoMarcacion.ENTRADA;
            else if (actual.getHoraSalida() == null) tipo = TipoMarcacion.SALIDA;
            else throw new ConflictoException("Ya registraste entrada y salida el " + fecha);
        }
        String origen = paraOtro ? "RRHH" : "AUTOSERVICIO";

        if (tipo == TipoMarcacion.ENTRADA) {
            if (actual != null) {
                throw new ConflictoException("Ya existe una entrada el " + fecha + " a las " + actual.getHoraEntrada());
            }
            Marcacion m = new Marcacion();
            m.setTenantId(auth.tenantId());
            m.setEmpleadoId(empleadoId);
            m.setFecha(fecha);
            m.setHoraEntrada(hora);
            m.setEstado(EstadoMarcacion.ABIERTA);
            int tardanza = (int) Math.max(0, Duration.between(horaIngreso.plusMinutes(toleranciaMinutos), hora).toMinutes());
            m.setTardanzaMinutos(tardanza);
            m.setTarde(tardanza > 0);
            m.setArea(empleado == null ? null : empleado.getArea());
            m.setOrigen(origen);
            m.setRegistradoPor(auth.userId());
            return MarcacionResponse.de(repository.save(m));
        }

        if (actual == null) throw new ReglaNegocioException("No hay entrada registrada el " + fecha + "; marca primero la entrada");
        if (actual.getHoraSalida() != null) throw new ConflictoException("Ya existe una salida registrada el " + fecha);
        if (hora.isBefore(actual.getHoraEntrada())) {
            throw new IllegalArgumentException("La salida no puede ser antes de la entrada (" + actual.getHoraEntrada() + ")");
        }
        actual.setHoraSalida(hora);
        actual.setHoras(BigDecimal.valueOf(Duration.between(actual.getHoraEntrada(), hora).toMinutes())
                .divide(BigDecimal.valueOf(60), 2, RoundingMode.HALF_UP));
        actual.setEstado(EstadoMarcacion.CERRADA);
        return MarcacionResponse.de(repository.save(actual));
    }

    /** Historial de un empleado (por defecto, los últimos 31 días). */
    @Transactional(readOnly = true)
    public HistorialMarcacionesResponse historial(AuthContext auth, String empleadoId, LocalDate desde, LocalDate hasta,
                                                  Integer page, Integer size) {
        String emp = empleadoId != null ? empleadoId : auth.exigirEmpleadoPropio();
        auth.exigirPropioOSupervisor(emp, "Solo puedes ver tus propias marcaciones");
        LocalDate h = hasta != null ? hasta : LocalDate.now(clock.withZone(zona));
        LocalDate d = desde != null ? desde : h.minusDays(30);
        if (d.isAfter(h)) throw new IllegalArgumentException("'desde' no puede ser posterior a 'hasta'");
        List<MarcacionResponse> items = repository
                .findByTenantIdAndEmpleadoIdAndFechaBetweenOrderByFechaDesc(auth.tenantId(), emp, d, h)
                .stream().map(MarcacionResponse::de).toList();
        BigDecimal horas = items.stream().map(m -> m.horas() == null ? BigDecimal.ZERO : m.horas()).reduce(BigDecimal.ZERO, BigDecimal::add);
        long tardanzas = items.stream().filter(m -> Boolean.TRUE.equals(m.tarde())).count();
        return new HistorialMarcacionesResponse(emp, d, h, items.size(), horas, tardanzas,
                PaginaResponse.deLista(items, Utils.pagina(page), Utils.tamanoPagina(size)));
    }

    /** Todas las marcaciones de un día (admin_rrhh / gerente). */
    @Transactional(readOnly = true)
    public PaginaResponse<MarcacionResponse> delDia(AuthContext auth, LocalDate fecha, Integer page, Integer size) {
        auth.exigirRol(AuthContext.ADMIN_RRHH, AuthContext.GERENTE);
        LocalDate f = fecha != null ? fecha : LocalDate.now(clock.withZone(zona));
        return PaginaResponse.de(repository.findByTenantIdAndFechaOrderByEmpleadoIdAsc(auth.tenantId(), f,
                PageRequest.of(Utils.pagina(page), Utils.tamanoPagina(size))), MarcacionResponse::de);
    }
}
