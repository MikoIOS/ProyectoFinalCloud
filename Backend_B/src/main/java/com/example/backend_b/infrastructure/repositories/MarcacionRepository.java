package com.example.backend_b.infrastructure.repositories;

import com.example.backend_b.entities.Marcacion;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface MarcacionRepository extends JpaRepository<Marcacion, Long> {
    Optional<Marcacion> findByTenantIdAndEmpleadoIdAndFecha(String tenantId, String empleadoId, LocalDate fecha);

    List<Marcacion> findByTenantIdAndEmpleadoIdAndFechaBetweenOrderByFechaDesc(String tenantId, String empleadoId, LocalDate desde, LocalDate hasta);

    Page<Marcacion> findByTenantIdAndFechaOrderByEmpleadoIdAsc(String tenantId, LocalDate fecha, Pageable pageable);

    List<Marcacion> findByTenantIdAndFechaBetweenOrderByFechaAscEmpleadoIdAsc(String tenantId, LocalDate desde, LocalDate hasta);

    long countByTenantIdAndFecha(String tenantId, LocalDate fecha);

    long countByTenantIdAndFechaAndTardeTrue(String tenantId, LocalDate fecha);
}
