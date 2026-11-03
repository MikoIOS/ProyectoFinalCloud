package com.example.backend_b.services;

import com.example.backend_b.common.Enums.EstadoAusencia;
import com.example.backend_b.common.Enums.EstadoEmpleado;
import com.example.backend_b.common.Enums.TipoAusencia;
import com.example.backend_b.common.Utils;
import com.example.backend_b.common.exception.AccesoDenegadoException;
import com.example.backend_b.common.exception.ConflictoException;
import com.example.backend_b.common.exception.ReglaNegocioException;
import com.example.backend_b.common.exception.ResourceNotFoundException;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.entities.Ausencia;
import com.example.backend_b.entities.Empleado;
import com.example.backend_b.infrastructure.DTOs.Response.AusenciaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.PaginaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.SaldoVacacionesResponse;
import com.example.backend_b.infrastructure.DTOs.request.AusenciaRequest;
import com.example.backend_b.infrastructure.DTOs.request.CambiarEstadoAusenciaRequest;
import com.example.backend_b.infrastructure.repositories.AusenciaRepository;
import com.example.backend_b.infrastructure.repositories.EmpleadoRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Solicitudes de ausencia: el empleado solicita, su jefe directo (o RR.HH.) aprueba o rechaza.
 * Estados: PENDIENTE → APROBADA | RECHAZADA | CANCELADA.
 * Publica AusenciaSolicitada, AusenciaAprobada y AusenciaRechazada.
 */
@Service
public class AusenciaService {

    public static final String ORIGEN = "ms-asistencia";
    private static final int MAX_DIAS_SOLICITUD = 90;
    private static final List<EstadoAusencia> VIGENTES = List.of(EstadoAusencia.PENDIENTE, EstadoAusencia.APROBADA);

    private final AusenciaRepository repository;
    private final EmpleadoRepository empleadoRepo;
    private final EventoPublisher eventos;
    private final Clock clock;
    private final ZoneId zona;
    private final int diasVacacionesAnuales;

    public AusenciaService(AusenciaRepository repository, EmpleadoRepository empleadoRepo, EventoPublisher eventos,
                           Clock clock, ZoneId zona,
                           @Value("${hcm.asistencia.dias-vacaciones-anuales:30}") int diasVacacionesAnuales) {
        this.repository = repository;
        this.empleadoRepo = empleadoRepo;
        this.eventos = eventos;
        this.clock = clock;
        this.zona = zona;
        this.diasVacacionesAnuales = diasVacacionesAnuales;
    }

    @Transactional
    public AusenciaResponse solicitar(AuthContext auth, AusenciaRequest dto) {
        String empleadoId;
        if (dto.getEmpleadoId() != null && !auth.esElEmpleado(dto.getEmpleadoId())) {
            auth.exigirRol(AuthContext.ADMIN_RRHH);
            empleadoId = dto.getEmpleadoId();
        } else {
            empleadoId = auth.exigirEmpleadoPropio();
        }
        LocalDate desde = dto.getDesde(), hasta = dto.getHasta();
        if (hasta.isBefore(desde)) throw new IllegalArgumentException("La fecha de fin no puede ser anterior a la de inicio");
        int dias = (int) ChronoUnit.DAYS.between(desde, hasta) + 1; // días calendario (régimen peruano)
        if (dias > MAX_DIAS_SOLICITUD) throw new IllegalArgumentException("Una solicitud no puede superar " + MAX_DIAS_SOLICITUD + " días");
        LocalDate hoy = LocalDate.now(clock.withZone(zona));
        if (!auth.esAdmin() && desde.isBefore(hoy.minusDays(30))) {
            throw new ReglaNegocioException("No se pueden solicitar ausencias con más de 30 días de antigüedad");
        }

        Empleado empleado = empleadoRepo.findByTenantIdAndEmpleadoId(auth.tenantId(), empleadoId).orElse(null);
        if (empleado != null && empleado.getEstado() == EstadoEmpleado.CESADO) {
            throw new ReglaNegocioException("El empleado " + empleadoId + " está cesado");
        }
        List<Ausencia> cruces = repository.superpuestas(auth.tenantId(), empleadoId, VIGENTES, desde, hasta);
        if (!cruces.isEmpty()) {
            Ausencia c = cruces.get(0);
            throw new ConflictoException("Se cruza con la ausencia " + c.getId() + " (" + c.getDesde() + " a " + c.getHasta() + ", " + c.getEstado() + ")");
        }
        if (dto.getTipo() == TipoAusencia.VACACIONES) {
            SaldoVacacionesResponse saldo = calcularSaldo(auth.tenantId(), empleadoId, empleado);
            if (dias > saldo.diasDisponibles()) {
                throw new ReglaNegocioException("Solicitas " + dias + " días de vacaciones y tienes " + saldo.diasDisponibles() + " disponibles");
            }
        }

        String jefe = empleado == null ? null : empleado.getJefeId();
        Ausencia a = new Ausencia();
        a.setTenantId(auth.tenantId());
        a.setEmpleadoId(empleadoId);
        a.setNombreEmpleado(empleado == null ? empleadoId : empleado.getNombreCompleto());
        a.setTipo(dto.getTipo());
        a.setConGoce(dto.getTipo().isConGoce());
        a.setDesde(desde);
        a.setHasta(hasta);
        a.setDias(dias);
        a.setMotivo(dto.getMotivo());
        a.setEstado(EstadoAusencia.PENDIENTE);
        // Sin jefe (o si es su propio jefe) la solicitud va a la bandeja de RR.HH. (aprobadorId = null)
        a.setAprobadorId(jefe == null || jefe.equals(empleadoId) ? null : jefe);
        a.setSolicitadoPor(auth.userId());
        a.setSolicitadoEn(clock.instant());
        a = repository.save(a);

        Map<String, Object> datos = datosEvento(a);
        datos.put("mensaje", "Nueva solicitud de " + texto(a.getTipo()) + " de " + a.getNombreEmpleado()
                + " (" + desde + " a " + hasta + ")");
        eventos.publicar("AusenciaSolicitada", auth.tenantId(), ORIGEN, datos);
        return AusenciaResponse.de(a);
    }

    @Transactional
    public AusenciaResponse cambiarEstado(AuthContext auth, Long id, CambiarEstadoAusenciaRequest dto) {
        EstadoAusencia nuevo = dto.getEstado();
        if (nuevo == EstadoAusencia.PENDIENTE) throw new IllegalArgumentException("No se puede volver a PENDIENTE");
        Ausencia a = repository.findByIdAndTenantId(id, auth.tenantId())
                .orElseThrow(() -> new ResourceNotFoundException("Ausencia no encontrada con ID: " + id));
        if (a.getEstado() != EstadoAusencia.PENDIENTE) throw new ConflictoException("La ausencia ya está " + a.getEstado());

        if (nuevo == EstadoAusencia.CANCELADA) {
            if (!auth.esElEmpleado(a.getEmpleadoId()) && !auth.esAdmin()) {
                throw new AccesoDenegadoException("Solo el solicitante o RR.HH. pueden cancelar la solicitud");
            }
        } else {
            boolean esAprobador = a.getAprobadorId() != null && auth.esElEmpleado(a.getAprobadorId());
            if (!esAprobador && !auth.esAdmin()) {
                throw new AccesoDenegadoException("Solo el jefe directo (" + (a.getAprobadorId() == null ? "RR.HH." : a.getAprobadorId())
                        + ") o RR.HH. pueden resolver esta solicitud");
            }
            if (auth.esElEmpleado(a.getEmpleadoId())) throw new AccesoDenegadoException("No puedes resolver tu propia solicitud");
        }

        if (nuevo == EstadoAusencia.APROBADA && a.getTipo() == TipoAusencia.VACACIONES) {
            Empleado e = empleadoRepo.findByTenantIdAndEmpleadoId(auth.tenantId(), a.getEmpleadoId()).orElseGet(() -> {
                Empleado nuevoEmp = new Empleado();
                nuevoEmp.setTenantId(auth.tenantId());
                nuevoEmp.setEmpleadoId(a.getEmpleadoId());
                nuevoEmp.setEstado(EstadoEmpleado.ACTIVO);
                return nuevoEmp;
            });
            // el saldo "disponible" ya descuenta esta solicitud por estar PENDIENTE
            if (calcularSaldo(auth.tenantId(), a.getEmpleadoId(), e).diasDisponibles() < 0) {
                throw new ReglaNegocioException("El empleado ya no tiene saldo de vacaciones suficiente");
            }
            if (e.getDiasVacacionesAsignados() == null) e.setDiasVacacionesAsignados(diasVacacionesAnuales);
            e.setDiasVacacionesUsados((e.getDiasVacacionesUsados() == null ? 0 : e.getDiasVacacionesUsados()) + a.getDias());
            empleadoRepo.save(e);
        }
        a.setEstado(nuevo);
        a.setComentario(dto.getComentario());
        a.setResueltoPor(auth.userId());
        a.setResueltoPorEmpleado(auth.empleadoId());
        a.setResueltoEn(clock.instant());
        Ausencia guardada = repository.save(a);

        if (nuevo != EstadoAusencia.CANCELADA) {
            Map<String, Object> datos = datosEvento(guardada);
            datos.put("comentario", dto.getComentario());
            datos.put("mensaje", "Tu solicitud de " + texto(guardada.getTipo()) + " (" + guardada.getDesde() + " a "
                    + guardada.getHasta() + ") fue " + (nuevo == EstadoAusencia.APROBADA ? "aprobada" : "rechazada"));
            // AusenciaAprobada sin goce → EventosInternosListener registra el descuento en nóminas (misma transacción)
            eventos.publicar(nuevo == EstadoAusencia.APROBADA ? "AusenciaAprobada" : "AusenciaRechazada",
                    auth.tenantId(), ORIGEN, datos);
        }
        return AusenciaResponse.de(guardada);
    }

    @Transactional(readOnly = true)
    public AusenciaResponse obtener(AuthContext auth, Long id) {
        Ausencia a = repository.findByIdAndTenantId(id, auth.tenantId())
                .orElseThrow(() -> new ResourceNotFoundException("Ausencia no encontrada con ID: " + id));
        boolean esAprobador = a.getAprobadorId() != null && auth.esElEmpleado(a.getAprobadorId());
        if (!auth.esSupervisor() && !auth.esElEmpleado(a.getEmpleadoId()) && !esAprobador) {
            throw new AccesoDenegadoException("No puedes ver esta solicitud");
        }
        return AusenciaResponse.de(a);
    }

    /** Con empleadoId: sus ausencias. Sin empleadoId: todas (supervisor) o las propias (empleado). */
    @Transactional(readOnly = true)
    public PaginaResponse<AusenciaResponse> listar(AuthContext auth, String empleadoId, EstadoAusencia estado,
                                                   TipoAusencia tipo, Integer page, Integer size) {
        int pg = Utils.pagina(page), sz = Utils.tamanoPagina(size);
        String emp = empleadoId;
        if (emp == null && !auth.esSupervisor()) emp = auth.exigirEmpleadoPropio();
        if (emp != null) {
            auth.exigirPropioOSupervisor(emp, "Solo puedes ver tus propias ausencias");
            List<AusenciaResponse> items = repository.findByTenantIdAndEmpleadoIdOrderByDesdeDesc(auth.tenantId(), emp).stream()
                    .filter(a -> estado == null || a.getEstado() == estado)
                    .filter(a -> tipo == null || a.getTipo() == tipo)
                    .map(AusenciaResponse::de).toList();
            return PaginaResponse.deLista(items, pg, sz);
        }
        return PaginaResponse.de(repository.buscar(auth.tenantId(), estado, tipo, PageRequest.of(pg, sz)), AusenciaResponse::de);
    }

    /** Bandeja de aprobación: la del jefe; admin_rrhh ve la de RR.HH. o, con todas=true, todas las pendientes. */
    @Transactional(readOnly = true)
    public PaginaResponse<AusenciaResponse> pendientes(AuthContext auth, boolean todas, Integer page, Integer size) {
        Pageable p = PageRequest.of(Utils.pagina(page), Utils.tamanoPagina(size));
        if (auth.esAdmin()) {
            return PaginaResponse.de(todas
                    ? repository.findByTenantIdAndEstadoOrderBySolicitadoEnAsc(auth.tenantId(), EstadoAusencia.PENDIENTE, p)
                    : repository.findByTenantIdAndEstadoAndAprobadorIdIsNullOrderBySolicitadoEnAsc(auth.tenantId(), EstadoAusencia.PENDIENTE, p),
                    AusenciaResponse::de);
        }
        return PaginaResponse.de(repository.findByTenantIdAndEstadoAndAprobadorIdOrderBySolicitadoEnAsc(
                auth.tenantId(), EstadoAusencia.PENDIENTE, auth.exigirEmpleadoPropio(), p), AusenciaResponse::de);
    }

    @Transactional(readOnly = true)
    public SaldoVacacionesResponse saldo(AuthContext auth, String empleadoId) {
        auth.exigirPropioOSupervisor(empleadoId, "Solo puedes ver tu propio saldo");
        Empleado e = empleadoRepo.findByTenantIdAndEmpleadoId(auth.tenantId(), empleadoId).orElse(null);
        return calcularSaldo(auth.tenantId(), empleadoId, e);
    }

    SaldoVacacionesResponse calcularSaldo(String tenantId, String empleadoId, Empleado e) {
        int asignados = e == null || e.getDiasVacacionesAsignados() == null ? diasVacacionesAnuales : e.getDiasVacacionesAsignados();
        int usados = e == null || e.getDiasVacacionesUsados() == null ? 0 : e.getDiasVacacionesUsados();
        Number pend = repository.sumarDias(tenantId, empleadoId, EstadoAusencia.PENDIENTE, TipoAusencia.VACACIONES);
        int pendientes = pend == null ? 0 : pend.intValue();
        return new SaldoVacacionesResponse(empleadoId, asignados, usados, pendientes, asignados - usados - pendientes);
    }

    private static Map<String, Object> datosEvento(Ausencia a) {
        Map<String, Object> d = new LinkedHashMap<>();
        d.put("ausencia_id", a.getId());
        d.put("empleado_id", a.getEmpleadoId());
        d.put("nombre_empleado", a.getNombreEmpleado());
        d.put("tipo", a.getTipo().name());
        d.put("con_goce", a.getConGoce());
        d.put("desde", a.getDesde());
        d.put("hasta", a.getHasta());
        d.put("dias", a.getDias());
        d.put("estado", a.getEstado().name());
        d.put("aprobador_id", a.getAprobadorId());
        return d;
    }

    private static String texto(TipoAusencia t) {
        return t.name().toLowerCase().replace('_', ' ');
    }
}
