package com.example.backend_b.infrastructure.repositories;

import com.example.backend_b.entities.ConceptoNomina;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ConceptoNominaRepository extends JpaRepository<ConceptoNomina, Long> {
    List<ConceptoNomina> findByTenantIdAndPeriodo(String tenantId, String periodo);

    List<ConceptoNomina> findByTenantIdAndPeriodoAndEmpleadoId(String tenantId, String periodo, String empleadoId);

    boolean existsByTenantIdAndPeriodoAndEmpleadoIdAndReferencia(String tenantId, String periodo, String empleadoId, String referencia);
}
