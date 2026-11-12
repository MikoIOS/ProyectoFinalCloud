package com.example.backend_b.entities;

import com.example.backend_b.common.Enums.OrigenConcepto;
import com.example.backend_b.common.Enums.TipoConcepto;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/** Bono, descuento o días sin goce que se aplican a la planilla de un periodo. */
@Entity
@Table(name = "conceptos_nomina",
        indexes = {@Index(name = "ix_conceptos_tenant_periodo", columnList = "tenant_id, periodo")})
@Getter
@Setter
@NoArgsConstructor
public class ConceptoNomina {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "conceptos_nomina_seq")
    @SequenceGenerator(name = "conceptos_nomina_seq", sequenceName = "conceptos_nomina_seq", allocationSize = 50)
    private Long id;

    @Column(name = "tenant_id", nullable = false, length = 40)
    private String tenantId;

    @Column(name = "empleado_id", nullable = false, length = 40)
    private String empleadoId;

    @Column(name = "periodo", nullable = false, length = 7)
    private String periodo;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private TipoConcepto tipo;

    @Column(length = 120)
    private String concepto;

    @Column(precision = 12, scale = 2)
    private BigDecimal monto;

    private Integer dias;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private OrigenConcepto origen;

    @Column(length = 60)
    private String referencia;

    @Column(length = 60)
    private String creadoPor;

    private Instant creadoEn;
}
