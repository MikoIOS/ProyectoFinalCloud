package com.example.backend_b.entities;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/** Liquidación referencial por cese (vacaciones, CTS y gratificación truncas). */
@Entity
@Table(name = "liquidaciones",
        uniqueConstraints = {@UniqueConstraint(name = "uk_liquidaciones_tenant_empleado", columnNames = {"tenant_id", "empleado_id"})})
@Getter
@Setter
@NoArgsConstructor
public class Liquidacion {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "liquidaciones_seq")
    @SequenceGenerator(name = "liquidaciones_seq", sequenceName = "liquidaciones_seq", allocationSize = 50)
    private Long id;

    @Column(name = "tenant_id", nullable = false, length = 40)
    private String tenantId;

    @Column(name = "empleado_id", nullable = false, length = 40)
    private String empleadoId;

    private LocalDate fechaCese;

    @Column(length = 200)
    private String motivo;

    @Column(precision = 12, scale = 2)
    private BigDecimal vacacionesTruncas;

    @Column(precision = 12, scale = 2)
    private BigDecimal ctsTrunca;

    @Column(precision = 12, scale = 2)
    private BigDecimal gratificacionTrunca;

    @Column(precision = 12, scale = 2)
    private BigDecimal total;

    private Instant calculadoEn;
}
