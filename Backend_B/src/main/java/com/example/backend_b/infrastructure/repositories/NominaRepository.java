package com.example.backend_b.infrastructure.repositories;

import com.example.backend_b.entities.Nomina;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface NominaRepository extends JpaRepository<Nomina, Long> {
    Optional<Nomina> findByIdAndTenantId(Long id, String tenantId);

    Optional<Nomina> findByTenantIdAndPeriodoAndEmpleadoId(String tenantId, String periodo, String empleadoId);

    Page<Nomina> findByTenantIdAndPeriodo(String tenantId, String periodo, Pageable pageable);

    Page<Nomina> findByTenantIdAndPeriodoAndArea(String tenantId, String periodo, String area, Pageable pageable);

    Page<Nomina> findByTenantIdAndEmpleadoIdOrderByPeriodoDesc(String tenantId, String empleadoId, Pageable pageable);

    long countByTenantIdAndPeriodo(String tenantId, String periodo);

    /** Borra las nóminas de un periodo (al recalcular con forzar=true). Las líneas se borran antes con NominaDetalleRepository. */
    @Modifying
    @Query("delete from Nomina n where n.tenantId = :tenantId and n.periodo = :periodo")
    int borrarPeriodo(@Param("tenantId") String tenantId, @Param("periodo") String periodo);
}
