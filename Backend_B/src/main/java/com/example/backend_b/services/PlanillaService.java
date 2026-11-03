package com.example.backend_b.services;

import com.example.backend_b.common.Enums.EstadoEmpleado;
import com.example.backend_b.common.Enums.EstadoPlanilla;
import com.example.backend_b.common.Utils;
import com.example.backend_b.common.exception.ConflictoException;
import com.example.backend_b.common.exception.ReglaNegocioException;
import com.example.backend_b.common.exception.ResourceNotFoundException;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.entities.Planilla;
import com.example.backend_b.infrastructure.DTOs.Response.PaginaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.PlanillaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.ResumenNominasResponse;
import com.example.backend_b.infrastructure.DTOs.request.GenerarPlanillaRequest;
import com.example.backend_b.infrastructure.repositories.EmpleadoRepository;
import com.example.backend_b.infrastructure.repositories.PlanillaRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.UUID;

/**
 * Planilla mensual. La generación es asíncrona: POST /generar responde 202 con la cabecera en
 * EN_PROCESO y {@link PlanillaWorker} calcula las nóminas en segundo plano, por lotes. El front
 * consulta GET /planillas/{periodo} hasta que el estado sea GENERADA.
 */
@Service
public class PlanillaService {

    private static final Duration PROCESO_COLGADO = Duration.ofMinutes(15);

    private final PlanillaRepository planillaRepo;
    private final EmpleadoRepository empleadoRepo;
    private final PlanillaWorker worker;
    private final Clock clock;
    private final ZoneId zona;

    public PlanillaService(PlanillaRepository planillaRepo, EmpleadoRepository empleadoRepo, PlanillaWorker worker,
                           Clock clock, ZoneId zona) {
        this.planillaRepo = planillaRepo;
        this.empleadoRepo = empleadoRepo;
        this.worker = worker;
        this.clock = clock;
        this.zona = zona;
    }

    /** No es @Transactional a propósito: la cabecera debe quedar guardada antes de que arranque el worker. */
    public PlanillaResponse generar(AuthContext auth, GenerarPlanillaRequest dto) {
        auth.exigirRol(AuthContext.ADMIN_RRHH);
        YearMonth periodo = Utils.periodo(dto.getPeriodo());
        if (periodo.isAfter(YearMonth.now(clock.withZone(zona)).plusMonths(1))) {
            throw new ReglaNegocioException("No se puede generar la planilla de un periodo tan lejano: " + periodo);
        }
        boolean forzar = Boolean.TRUE.equals(dto.getForzar());
        Instant ahora = clock.instant();

        Planilla p = planillaRepo.findByTenantIdAndPeriodo(auth.tenantId(), periodo.toString()).orElse(null);
        if (p != null) {
            boolean colgada = p.getIniciadoEn() != null && p.getIniciadoEn().plus(PROCESO_COLGADO).isBefore(ahora);
            if (p.getEstado() == EstadoPlanilla.EN_PROCESO && !colgada) {
                throw new ConflictoException("La planilla " + periodo + " se está generando (" + p.getProcesados() + "/" + p.getTotalEmpleados() + ")");
            }
            if (p.getEstado() == EstadoPlanilla.PAGADA) {
                throw new ReglaNegocioException("La planilla " + periodo + " ya fue pagada y no se puede recalcular");
            }
            if (p.getEstado() == EstadoPlanilla.GENERADA && !forzar) {
                throw new ConflictoException("La planilla " + periodo + " ya existe. Envía \"forzar\": true para recalcularla");
            }
        } else {
            p = new Planilla();
            p.setTenantId(auth.tenantId());
            p.setPeriodo(periodo.toString());
        }
        p.setEstado(EstadoPlanilla.EN_PROCESO);
        p.setEjecucionId(UUID.randomUUID().toString());
        p.setTotalEmpleados(0);
        p.setProcesados(0);
        p.setTotalBruto(Utils.cero());
        p.setTotalDescuentos(Utils.cero());
        p.setTotalNeto(Utils.cero());
        p.setTotalEssalud(Utils.cero());
        p.setIniciadoEn(ahora);
        p.setCompletadoEn(null);
        p.setMensajeError(null);
        p.setSolicitadoPor(auth.userId());
        p = planillaRepo.save(p);

        worker.procesar(p.getId(), p.getEjecucionId());
        return PlanillaResponse.de(p);
    }

    @Transactional(readOnly = true)
    public PlanillaResponse obtener(AuthContext auth, String periodo) {
        auth.exigirRol(AuthContext.ADMIN_RRHH, AuthContext.GERENTE);
        Utils.periodo(periodo);
        return planillaRepo.findByTenantIdAndPeriodo(auth.tenantId(), periodo).map(PlanillaResponse::de)
                .orElseThrow(() -> new ResourceNotFoundException("No hay planilla para " + periodo));
    }

    @Transactional(readOnly = true)
    public PaginaResponse<PlanillaResponse> listar(AuthContext auth, Integer page, Integer size) {
        auth.exigirRol(AuthContext.ADMIN_RRHH, AuthContext.GERENTE);
        return PaginaResponse.de(planillaRepo.findByTenantIdOrderByPeriodoDesc(auth.tenantId(),
                PageRequest.of(Utils.pagina(page), Utils.tamanoPagina(size))), PlanillaResponse::de);
    }

    /** Dashboard: la planilla pedida o la más reciente. */
    @Transactional(readOnly = true)
    public ResumenNominasResponse resumen(AuthContext auth, String periodo) {
        auth.exigirRol(AuthContext.ADMIN_RRHH, AuthContext.GERENTE);
        Planilla p;
        String per;
        if (periodo == null || periodo.isBlank()) {
            p = planillaRepo.findFirstByTenantIdOrderByPeriodoDesc(auth.tenantId()).orElse(null);
            per = p != null ? p.getPeriodo() : YearMonth.now(clock.withZone(zona)).toString();
        } else {
            per = Utils.periodo(periodo).toString();
            p = planillaRepo.findByTenantIdAndPeriodo(auth.tenantId(), per).orElse(null);
        }
        long activos = empleadoRepo.countByTenantIdAndEstado(auth.tenantId(), EstadoEmpleado.ACTIVO);
        if (p == null) {
            return new ResumenNominasResponse(per, null, 0, Utils.cero(), Utils.cero(), Utils.cero(), Utils.cero(), activos);
        }
        return new ResumenNominasResponse(per, p.getEstado(), p.getProcesados(), p.getTotalBruto(), p.getTotalDescuentos(),
                p.getTotalNeto(), p.getTotalEssalud(), activos);
    }
}
