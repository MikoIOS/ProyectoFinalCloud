package com.example.backend_b.infrastructure.repositories;

import com.example.backend_b.entities.NominaDetalle;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface NominaDetalleRepository extends JpaRepository<NominaDetalle, Long> {
    @Modifying
    @Query("delete from NominaDetalle d where d.nomina.id in (select n.id from Nomina n where n.tenantId = :tenantId and n.periodo = :periodo)")
    int borrarPeriodo(@Param("tenantId") String tenantId, @Param("periodo") String periodo);
}
