package com.example.backend_b.entities;

import com.example.backend_b.common.Enums.EstadoPlanilla;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/** Cabecera de la planilla mensual de un tenant: estado de la generación y totales. */
@Entity
@Table(name = "planillas",
        uniqueConstraints = {@UniqueConstraint(name = "uk_planillas_tenant_periodo", columnNames = {"tenant_id", "periodo"})})
@Getter
@Setter
@NoArgsConstructor
public class Planilla {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "planillas_seq")
    @SequenceGenerator(name = "planillas_seq", sequenceName = "planillas_seq", allocationSize = 50)
    private Long id;

    @Column(name = "tenant_id", nullable = false, length = 40)
    private String tenantId;

    @Column(name = "periodo", nullable = false, length = 7)
    private String periodo;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private EstadoPlanilla estado;

    @Column(length = 40)
    private String ejecucionId;

    private Integer totalEmpleados;

    private Integer procesados;

    @Column(precision = 12, scale = 2)
    private BigDecimal totalBruto;

    @Column(precision = 12, scale = 2)
    private BigDecimal totalDescuentos;

    @Column(precision = 12, scale = 2)
    private BigDecimal totalNeto;

    @Column(precision = 12, scale = 2)
    private BigDecimal totalEssalud;

    private Instant iniciadoEn;

    private Instant completadoEn;

    @Column(length = 60)
    private String solicitadoPor;

    @Column(length = 500)
    private String mensajeError;

    @Version
    private Long version;
}
