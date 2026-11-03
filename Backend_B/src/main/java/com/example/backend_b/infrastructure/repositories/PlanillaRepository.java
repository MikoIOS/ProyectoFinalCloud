package com.example.backend_b.infrastructure.repositories;

import com.example.backend_b.entities.Planilla;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface PlanillaRepository extends JpaRepository<Planilla, Long> {
    Optional<Planilla> findByTenantIdAndPeriodo(String tenantId, String periodo);

    Optional<Planilla> findFirstByTenantIdOrderByPeriodoDesc(String tenantId);

    Page<Planilla> findByTenantIdOrderByPeriodoDesc(String tenantId, Pageable pageable);
}
