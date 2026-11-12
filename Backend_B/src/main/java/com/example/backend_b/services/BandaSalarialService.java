package com.example.backend_b.services;

import com.example.backend_b.common.Utils;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.entities.BandaSalarial;
import com.example.backend_b.infrastructure.DTOs.Response.BandaSalarialResponse;
import com.example.backend_b.infrastructure.DTOs.request.BandaSalarialRequest;
import com.example.backend_b.infrastructure.repositories.BandaSalarialRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.util.List;
import java.util.Locale;

/** Bandas salariales por cargo (referencia de compensación). */
@Service
public class BandaSalarialService {

    private final BandaSalarialRepository repository;
    private final Clock clock;

    public BandaSalarialService(BandaSalarialRepository repository, Clock clock) {
        this.repository = repository;
        this.clock = clock;
    }

    @Transactional(readOnly = true)
    public List<BandaSalarialResponse> listar(AuthContext auth) {
        auth.exigirRol(AuthContext.ADMIN_RRHH, AuthContext.GERENTE, AuthContext.RECLUTADOR);
        return repository.findByTenantIdOrderByCargoAsc(auth.tenantId()).stream().map(BandaSalarialResponse::de).toList();
    }

    /** Crea la banda del cargo o la actualiza si ya existe. */
    @Transactional
    public BandaSalarialResponse guardar(AuthContext auth, BandaSalarialRequest dto) {
        auth.exigirRol(AuthContext.ADMIN_RRHH);
        if (dto.getMinimo().compareTo(dto.getMaximo()) > 0) {
            throw new IllegalArgumentException("El mínimo no puede ser mayor que el máximo");
        }
        String cargo = dto.getCargo().trim();
        BandaSalarial b = repository.findByTenantIdAndCargo(auth.tenantId(), cargo).orElseGet(() -> {
            BandaSalarial nueva = new BandaSalarial();
            nueva.setTenantId(auth.tenantId());
            nueva.setCargo(cargo);
            return nueva;
        });
        b.setMinimo(Utils.dinero(dto.getMinimo()));
        b.setMaximo(Utils.dinero(dto.getMaximo()));
        b.setMoneda(dto.getMoneda() == null ? "PEN" : dto.getMoneda().toUpperCase(Locale.ROOT));
        b.setActualizadoEn(clock.instant());
        return BandaSalarialResponse.de(repository.save(b));
    }
}
