package com.example.backend_b.infrastructure.repositories;

import com.example.backend_b.common.Enums.EstadoAusencia;
import com.example.backend_b.common.Enums.TipoAusencia;
import com.example.backend_b.entities.Ausencia;
import java.time.LocalDate;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface AusenciaRepository extends JpaRepository<Ausencia, Long> {
    Optional<Ausencia> findByIdAndTenantId(Long id, String tenantId);

    List<Ausencia> findByTenantIdAndEmpleadoIdOrderByDesdeDesc(String tenantId, String empleadoId);

    List<Ausencia> findByTenantIdAndEmpleadoIdAndEstado(String tenantId, String empleadoId, EstadoAusencia estado);

    /** Bandeja de un jefe. */
    Page<Ausencia> findByTenantIdAndEstadoAndAprobadorIdOrderBySolicitadoEnAsc(String tenantId, EstadoAusencia estado, String aprobadorId, Pageable pageable);

    /** Bandeja de RR.HH.: solicitudes de empleados sin jefe asignado. */
    Page<Ausencia> findByTenantIdAndEstadoAndAprobadorIdIsNullOrderBySolicitadoEnAsc(String tenantId, EstadoAusencia estado, Pageable pageable);

    Page<Ausencia> findByTenantIdAndEstadoOrderBySolicitadoEnAsc(String tenantId, EstadoAusencia estado, Pageable pageable);

    long countByTenantIdAndEstado(String tenantId, EstadoAusencia estado);

    @Query("select a from Ausencia a where a.tenantId = :tenantId and (:estado is null or a.estado = :estado) "
            + "and (:tipo is null or a.tipo = :tipo) order by a.desde desc")
    Page<Ausencia> buscar(@Param("tenantId") String tenantId, @Param("estado") EstadoAusencia estado,
                          @Param("tipo") TipoAusencia tipo, Pageable pageable);

    /** Ausencias vigentes del empleado que se cruzan con [desde, hasta]. */
    @Query("select a from Ausencia a where a.tenantId = :tenantId and a.empleadoId = :empleadoId "
            + "and a.estado in :estados and a.desde <= :hasta and a.hasta >= :desde")
    List<Ausencia> superpuestas(@Param("tenantId") String tenantId, @Param("empleadoId") String empleadoId,
                                @Param("estados") Collection<EstadoAusencia> estados,
                                @Param("desde") LocalDate desde, @Param("hasta") LocalDate hasta);

    @Query("select coalesce(sum(a.dias), 0) from Ausencia a where a.tenantId = :tenantId and a.empleadoId = :empleadoId "
            + "and a.estado = :estado and a.tipo = :tipo")
    Number sumarDias(@Param("tenantId") String tenantId, @Param("empleadoId") String empleadoId,
                   @Param("estado") EstadoAusencia estado, @Param("tipo") TipoAusencia tipo);

    List<Ausencia> findByTenantIdAndDesdeLessThanEqualAndHastaGreaterThanEqualOrderByDesdeAsc(String tenantId, LocalDate fin, LocalDate inicio);
}
