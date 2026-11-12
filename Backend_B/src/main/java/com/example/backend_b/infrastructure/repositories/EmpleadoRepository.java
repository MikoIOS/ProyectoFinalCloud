package com.example.backend_b.infrastructure.repositories;

import com.example.backend_b.common.Enums.EstadoEmpleado;
import com.example.backend_b.entities.Empleado;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface EmpleadoRepository extends JpaRepository<Empleado, Long> {
    Optional<Empleado> findByTenantIdAndEmpleadoId(String tenantId, String empleadoId);

    List<Empleado> findByTenantIdOrderByEmpleadoIdAsc(String tenantId);

    long countByTenantIdAndEstado(String tenantId, EstadoEmpleado estado);

    long countByTenantId(String tenantId);
}
