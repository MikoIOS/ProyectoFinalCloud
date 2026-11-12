package com.example.backend_b.infrastructure.repositories;

import com.example.backend_b.entities.BandaSalarial;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface BandaSalarialRepository extends JpaRepository<BandaSalarial, Long> {
    List<BandaSalarial> findByTenantIdOrderByCargoAsc(String tenantId);

    Optional<BandaSalarial> findByTenantIdAndCargo(String tenantId, String cargo);
}
