package com.example.backend_b.services;

import com.example.backend_b.common.Utils;
import com.example.backend_b.common.exception.ResourceNotFoundException;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.entities.Nomina;
import com.example.backend_b.infrastructure.DTOs.Response.LiquidacionResponse;
import com.example.backend_b.infrastructure.DTOs.Response.NominaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.NominaResumenResponse;
import com.example.backend_b.infrastructure.DTOs.Response.NominasEmpleadoResponse;
import com.example.backend_b.infrastructure.DTOs.Response.PaginaResponse;
import com.example.backend_b.infrastructure.repositories.LiquidacionRepository;
import com.example.backend_b.infrastructure.repositories.NominaRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Consultas de nóminas y boletas. Todo se filtra por el tenant del token. */
@Service
public class NominaService {

    private final NominaRepository repository;
    private final LiquidacionRepository liquidacionRepo;
    private final BoletaPdfService boletaPdf;

    public NominaService(NominaRepository repository, LiquidacionRepository liquidacionRepo, BoletaPdfService boletaPdf) {
        this.repository = repository;
        this.liquidacionRepo = liquidacionRepo;
        this.boletaPdf = boletaPdf;
    }

    public record Boleta(String nombreArchivo, byte[] pdf) {}

    @Transactional(readOnly = true)
    public PaginaResponse<NominaResumenResponse> listarPeriodo(AuthContext auth, String periodo, String area, Integer page, Integer size) {
        auth.exigirRol(AuthContext.ADMIN_RRHH, AuthContext.GERENTE);
        Utils.periodo(periodo);
        Pageable p = PageRequest.of(Utils.pagina(page), Utils.tamanoPagina(size), Sort.by("empleadoId"));
        Page<Nomina> res = area == null || area.isBlank()
                ? repository.findByTenantIdAndPeriodo(auth.tenantId(), periodo, p)
                : repository.findByTenantIdAndPeriodoAndArea(auth.tenantId(), periodo, area, p);
        return PaginaResponse.de(res, NominaResumenResponse::de);
    }

    @Transactional(readOnly = true)
    public NominasEmpleadoResponse delEmpleado(AuthContext auth, String empleadoId, Integer page, Integer size) {
        auth.exigirPropioOSupervisor(empleadoId, "Solo puedes ver tus propias boletas");
        Page<Nomina> res = repository.findByTenantIdAndEmpleadoIdOrderByPeriodoDesc(auth.tenantId(), empleadoId,
                PageRequest.of(Utils.pagina(page), Utils.tamanoPagina(size)));
        LiquidacionResponse liq = liquidacionRepo.findByTenantIdAndEmpleadoId(auth.tenantId(), empleadoId)
                .map(LiquidacionResponse::de).orElse(null);
        return new NominasEmpleadoResponse(empleadoId, PaginaResponse.de(res, NominaResumenResponse::de), liq);
    }

    @Transactional(readOnly = true)
    public NominaResponse detalle(AuthContext auth, Long id) {
        return NominaResponse.de(buscar(auth, id));
    }

    @Transactional(readOnly = true)
    public Boleta boleta(AuthContext auth, Long id) {
        Nomina n = buscar(auth, id);
        return new Boleta("boleta-" + n.getPeriodo() + "-" + n.getEmpleadoId() + ".pdf", boletaPdf.generar(n));
    }

    private Nomina buscar(AuthContext auth, Long id) {
        Nomina n = repository.findByIdAndTenantId(id, auth.tenantId())
                .orElseThrow(() -> new ResourceNotFoundException("Nómina no encontrada con ID: " + id));
        auth.exigirPropioOSupervisor(n.getEmpleadoId(), "Solo puedes ver tus propias boletas");
        return n;
    }
}
