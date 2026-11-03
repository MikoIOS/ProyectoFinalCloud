package com.example.backend_b.infrastructure.repositories;

import com.example.backend_b.entities.Liquidacion;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface LiquidacionRepository extends JpaRepository<Liquidacion, Long> {
    Optional<Liquidacion> findByTenantIdAndEmpleadoId(String tenantId, String empleadoId);
}
