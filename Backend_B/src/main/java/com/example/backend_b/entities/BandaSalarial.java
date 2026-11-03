package com.example.backend_b.entities;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/** Banda salarial (rango de referencia) por cargo. */
@Entity
@Table(name = "bandas_salariales",
        uniqueConstraints = {@UniqueConstraint(name = "uk_bandas_tenant_cargo", columnNames = {"tenant_id", "cargo"})})
@Getter
@Setter
@NoArgsConstructor
public class BandaSalarial {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "bandas_salariales_seq")
    @SequenceGenerator(name = "bandas_salariales_seq", sequenceName = "bandas_salariales_seq", allocationSize = 50)
    private Long id;

    @Column(name = "tenant_id", nullable = false, length = 40)
    private String tenantId;

    @Column(name = "cargo", nullable = false, length = 80)
    private String cargo;

    @Column(precision = 12, scale = 2)
    private BigDecimal minimo;

    @Column(precision = 12, scale = 2)
    private BigDecimal maximo;

    @Column(length = 3)
    private String moneda;

    private Instant actualizadoEn;

    @Version
    private Long version;
}
