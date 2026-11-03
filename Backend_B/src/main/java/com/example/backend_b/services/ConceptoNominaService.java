package com.example.backend_b.services;

import com.example.backend_b.common.Enums.EstadoPlanilla;
import com.example.backend_b.common.Enums.OrigenConcepto;
import com.example.backend_b.common.Enums.TipoConcepto;
import com.example.backend_b.common.Utils;
import com.example.backend_b.common.exception.ReglaNegocioException;
import com.example.backend_b.common.exception.ResourceNotFoundException;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.entities.ConceptoNomina;
import com.example.backend_b.infrastructure.DTOs.Response.ConceptoNominaResponse;
import com.example.backend_b.infrastructure.DTOs.request.ConceptoNominaRequest;
import com.example.backend_b.infrastructure.repositories.ConceptoNominaRepository;
import com.example.backend_b.infrastructure.repositories.EmpleadoRepository;
import com.example.backend_b.infrastructure.repositories.PlanillaRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.temporal.ChronoUnit;
import java.util.List;

/** Bonos y descuentos manuales, y días sin goce que llegan de ausencias aprobadas. */
@Service
public class ConceptoNominaService {

    private static final Logger log = LoggerFactory.getLogger(ConceptoNominaService.class);

    private final ConceptoNominaRepository repository;
    private final EmpleadoRepository empleadoRepo;
    private final PlanillaRepository planillaRepo;
    private final Clock clock;

    public ConceptoNominaService(ConceptoNominaRepository repository, EmpleadoRepository empleadoRepo,
                                 PlanillaRepository planillaRepo, Clock clock) {
        this.repository = repository;
        this.empleadoRepo = empleadoRepo;
        this.planillaRepo = planillaRepo;
        this.clock = clock;
    }

    @Transactional
    public ConceptoNominaResponse crear(AuthContext auth, ConceptoNominaRequest dto) {
        auth.exigirRol(AuthContext.ADMIN_RRHH);
        if (dto.getTipo() == TipoConcepto.SIN_GOCE) {
            throw new IllegalArgumentException("Los días sin goce se registran aprobando una ausencia SIN_GOCE en asistencia");
        }
        Utils.periodo(dto.getPeriodo());
        empleadoRepo.findByTenantIdAndEmpleadoId(auth.tenantId(), dto.getEmpleadoId())
                .orElseThrow(() -> new ResourceNotFoundException("Empleado no encontrado: " + dto.getEmpleadoId()));
        planillaRepo.findByTenantIdAndPeriodo(auth.tenantId(), dto.getPeriodo()).ifPresent(p -> {
            if (p.getEstado() == EstadoPlanilla.PAGADA) {
                throw new ReglaNegocioException("La planilla " + dto.getPeriodo() + " ya fue pagada");
            }
        });
        ConceptoNomina c = new ConceptoNomina();
        c.setTenantId(auth.tenantId());
        c.setEmpleadoId(dto.getEmpleadoId());
        c.setPeriodo(dto.getPeriodo());
        c.setTipo(dto.getTipo());
        c.setConcepto(dto.getConcepto().trim());
        c.setMonto(Utils.dinero(dto.getMonto()));
        c.setOrigen(OrigenConcepto.MANUAL);
        c.setCreadoPor(auth.userId());
        c.setCreadoEn(clock.instant());
        return ConceptoNominaResponse.de(repository.save(c));
    }

    @Transactional(readOnly = true)
    public List<ConceptoNominaResponse> listar(AuthContext auth, String periodo, String empleadoId) {
        Utils.periodo(periodo);
        List<ConceptoNomina> items;
        if (empleadoId != null && !empleadoId.isBlank()) {
            auth.exigirPropioOSupervisor(empleadoId, "Solo puedes ver tus propios conceptos");
            items = repository.findByTenantIdAndPeriodoAndEmpleadoId(auth.tenantId(), periodo, empleadoId);
        } else {
            auth.exigirRol(AuthContext.ADMIN_RRHH, AuthContext.GERENTE);
            items = repository.findByTenantIdAndPeriodo(auth.tenantId(), periodo);
        }
        return items.stream().map(ConceptoNominaResponse::de).toList();
    }

    /**
     * AusenciaAprobada sin goce → un concepto SIN_GOCE por cada mes que toca la ausencia.
     * Idempotente: la referencia (id de ausencia) evita duplicados si el evento se repite.
     */
    @Transactional
    public int registrarSinGoce(String tenantId, String empleadoId, String ausenciaId, LocalDate desde, LocalDate hasta) {
        int creados = 0;
        for (YearMonth ym = YearMonth.from(desde); !ym.isAfter(YearMonth.from(hasta)); ym = ym.plusMonths(1)) {
            String periodo = ym.toString();
            String referencia = "AUSENCIA-" + ausenciaId;
            if (repository.existsByTenantIdAndPeriodoAndEmpleadoIdAndReferencia(tenantId, periodo, empleadoId, referencia)) continue;
            LocalDate ini = desde.isAfter(ym.atDay(1)) ? desde : ym.atDay(1);
            LocalDate fin = hasta.isBefore(ym.atEndOfMonth()) ? hasta : ym.atEndOfMonth();
            ConceptoNomina c = new ConceptoNomina();
            c.setTenantId(tenantId);
            c.setEmpleadoId(empleadoId);
            c.setPeriodo(periodo);
            c.setTipo(TipoConcepto.SIN_GOCE);
            c.setConcepto("Ausencia sin goce " + ini + " a " + fin);
            c.setDias((int) ChronoUnit.DAYS.between(ini, fin) + 1);
            c.setOrigen(OrigenConcepto.AUSENCIA);
            c.setReferencia(referencia);
            c.setCreadoEn(clock.instant());
            repository.save(c);
            creados++;
        }
        log.info("Días sin goce registrados para {}/{} (ausencia {}): {} periodo(s)", tenantId, empleadoId, ausenciaId, creados);
        return creados;
    }
}
